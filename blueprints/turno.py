import logging
from datetime import date

from flask import Blueprint, render_template, request, redirect, session, jsonify

from database import conectar
from utils.auth import requiere_login, requiere_staff
from utils.constants import ROLES_ADMIN_PM, TURNOS_CONCILIACION, TURNOS_CONCILIACION_LABELS, ROLES_OPERARIO_GAS
from utils import mailer
from utils.adjuntos import foto_valida, guardar_adjunto
from utils.despachos import insertar_despacho_con_numero
from utils.tarjetas import obtener_factor, calcular_usd_desde_litros
from utils.subinventarios import apartar_remanente_despacho, SubinventarioError

logger = logging.getLogger(__name__)

turno_bp = Blueprint("turno", __name__, url_prefix="/turno")


def _requiere_operario_gas():
    if "usuario" not in session:
        return redirect("/login")
    if session.get("rol") not in ROLES_OPERARIO_GAS:
        return redirect("/dashboard")
    return None


# ── Página principal ──────────────────────────────────────────────────────────

@turno_bp.route("/")
def index():
    redir = requiere_staff()
    if redir:
        return redir

    hoy = date.today().isoformat()
    rol_actual = session.get("rol")
    fecha = request.args.get("fecha", hoy).strip()
    turno = ""  # eliminado del flujo

    # Para operador_gasolinera: forzar su gasolinera; ignorar parámetro URL
    if rol_actual == "operador_gasolinera":
        gasolinera_id = str(session.get("gasolinera_id") or "")
    else:
        gasolinera_id = request.args.get("gasolinera_id", "").strip()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()

    cur.execute("SELECT id, nombre, codigo FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()

    cur.execute("""
        SELECT v.id, v.chapa, v.cliente_id, v.tipo_combustible,
               ch.nombre AS chofer_nombre
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        WHERE v.estado = 'activo'
        ORDER BY v.chapa ASC
    """)
    unidades = cur.fetchall()

    cur.execute("""
        SELECT t.id, t.numero_parcial, t.gasolinera_id, t.saldo_usable_l
        FROM tarjetas t
        WHERE t.estado = 'activa'
        ORDER BY t.numero_parcial ASC
    """)
    tarjetas = cur.fetchall()

    cur.execute("SELECT valor FROM configuracion WHERE clave = 'compra_minima_litros'")
    row_min = cur.fetchone()
    compra_minima = float(row_min["valor"]) if row_min else 0.0

    habilitaciones = []
    conciliacion_existente = None

    if gasolinera_id and fecha:
        condiciones = ["h.gasolinera_id = ?", "h.fecha_habilitacion = ?"]
        params = [gasolinera_id, fecha]
        if turno:
            # filtrar por habilitaciones del turno (aproximado: no tenemos campo turno en habilitaciones)
            pass

        cur.execute(f"""
            SELECT h.id, h.litros_autorizados, h.litros_despachados, h.estado,
                   cli.nombre AS cliente, v.chapa,
                   ch.nombre AS chofer,
                   t.numero_parcial AS tarjeta
            FROM habilitaciones h
            JOIN clientes cli ON cli.id = h.cliente_id
            JOIN vehiculos v ON v.id = h.unidad_id
            LEFT JOIN choferes ch ON ch.id = v.chofer_id
            JOIN tarjetas t ON t.id = h.tarjeta_id
            WHERE {' AND '.join(condiciones)}
            ORDER BY h.id ASC
        """, params)
        habilitaciones = cur.fetchall()

        cur.execute("""
            SELECT * FROM conciliaciones
            WHERE gasolinera_id = ? AND fecha = ?
            ORDER BY id DESC LIMIT 1
        """, (gasolinera_id, fecha))
        conciliacion_existente = cur.fetchone()

    conn.close()

    return render_template(
        "turno/index.html",
        gasolineras=gasolineras,
        clientes=clientes,
        unidades=unidades,
        tarjetas=tarjetas,
        habilitaciones=habilitaciones,
        gasolinera_id=gasolinera_id,
        fecha=fecha,
        hoy=hoy,
        conciliacion_existente=conciliacion_existente,
        compra_minima=compra_minima,
        rol=session.get("rol"),
    )


# ── API: Crear habilitación inline (AJAX) ─────────────────────────────────────

@turno_bp.route("/api/habilitacion", methods=["POST"])
def api_crear_habilitacion():
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401
    if session.get("rol") not in ROLES_ADMIN_PM:
        return jsonify({"error": "Solo admin y PM pueden crear habilitaciones"}), 403

    data = request.get_json(silent=True) or request.form
    cliente_id = data.get("cliente_id", "")
    unidad_id = data.get("unidad_id", "")
    gasolinera_id = data.get("gasolinera_id", "")
    tarjeta_id = data.get("tarjeta_id", "")
    litros_str = str(data.get("litros_autorizados", "0")).replace(",", ".")
    fecha = data.get("fecha", date.today().isoformat())

    if not all([cliente_id, unidad_id, gasolinera_id, tarjeta_id]):
        return jsonify({"error": "Faltan campos obligatorios"}), 400

    try:
        litros = float(litros_str)
    except ValueError:
        return jsonify({"error": "Litros inválidos"}), 400

    if litros <= 0:
        return jsonify({"error": "Los litros deben ser mayores a cero"}), 400

    conn = conectar()
    cur = conn.cursor()

    # Validar compra mínima
    cur.execute("SELECT valor FROM configuracion WHERE clave = 'compra_minima_litros'")
    row_min = cur.fetchone()
    if row_min:
        minimo = float(row_min["valor"])
        if litros < minimo:
            conn.close()
            return jsonify({"error": f"El mínimo de litros por habilitación es {minimo:,.0f} L"}), 400

    cur.execute("""
        INSERT INTO habilitaciones
            (cliente_id, unidad_id, gasolinera_id, tarjeta_id,
             litros_autorizados, fecha_habilitacion, estado, creado_por)
        VALUES (?, ?, ?, ?, ?, ?, 'pendiente', ?)
    """, (cliente_id, unidad_id, gasolinera_id, tarjeta_id,
          litros, fecha, session.get("user_id")))
    nuevo_id = cur.lastrowid

    cur.execute("""
        SELECT h.id, h.litros_autorizados, h.litros_despachados, h.estado,
               cli.nombre AS cliente, v.chapa,
               ch.nombre AS chofer,
               t.numero_parcial AS tarjeta
        FROM habilitaciones h
        JOIN clientes cli ON cli.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        WHERE h.id = ?
    """, (nuevo_id,))
    hab = cur.fetchone()
    conn.commit()
    conn.close()

    return jsonify({
        "id": hab["id"],
        "cliente": hab["cliente"],
        "chapa": hab["chapa"],
        "chofer": hab["chofer"] or "—",
        "tarjeta": hab["tarjeta"],
        "litros_autorizados": float(hab["litros_autorizados"]),
        "litros_despachados": float(hab["litros_despachados"]),
        "estado": hab["estado"],
    })


# ── API: Aprobar habilitación ─────────────────────────────────────────────────

@turno_bp.route("/api/<int:hab_id>/aprobar", methods=["POST"])
def api_aprobar(hab_id):
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401
    if session.get("rol") not in ROLES_ADMIN_PM:
        return jsonify({"error": "Solo admin y PM pueden aprobar"}), 403

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT h.estado, h.litros_autorizados,
               v.estado AS unidad_estado,
               ch.licencia_vencimiento,
               t.estado AS tarjeta_estado, t.saldo_usable_l
        FROM habilitaciones h
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        WHERE h.id = ?
    """, (hab_id,))
    hab = cur.fetchone()

    if not hab:
        conn.close()
        return jsonify({"error": "Habilitación no encontrada"}), 404
    if hab["estado"] != "pendiente":
        conn.close()
        return jsonify({"error": f"Estado actual: {hab['estado']}"}), 400

    litros = float(hab["litros_autorizados"])
    hoy_str = date.today().isoformat()

    if hab["unidad_estado"] != "activo":
        conn.close()
        return jsonify({"error": "La unidad no está activa"}), 400
    if hab["licencia_vencimiento"] and hab["licencia_vencimiento"] < hoy_str:
        conn.close()
        return jsonify({"error": f"Licencia del chofer vencida ({hab['licencia_vencimiento']})"}), 400
    if hab["tarjeta_estado"] != "activa":
        conn.close()
        return jsonify({"error": "La tarjeta no está activa"}), 400
    if float(hab["saldo_usable_l"]) < litros - 0.001:
        conn.close()
        return jsonify({"error": f"Saldo insuficiente: {float(hab['saldo_usable_l']):,.2f} L disponible"}), 400

    cur.execute("""
        UPDATE habilitaciones SET estado='aprobada', aprobado_por=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (session.get("user_id"), hab_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "estado": "aprobada"})


# ── API: Registrar despacho rápido ────────────────────────────────────────────

@turno_bp.route("/api/<int:hab_id>/despachar", methods=["POST"])
def api_despachar(hab_id):
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401

    litros_str = request.form.get("litros_despachados", "0").replace(",", ".")
    foto = request.files.get("foto_ticket")

    if foto and foto.filename and not foto_valida(foto):
        return jsonify({"error": "Formato de foto no válido. Use JPG, PNG o WEBP."}), 400

    try:
        litros = float(litros_str)
    except ValueError:
        return jsonify({"error": "Litros inválidos"}), 400

    if litros <= 0:
        return jsonify({"error": "Litros deben ser mayores a cero"}), 400

    conn = conectar()
    cur = conn.cursor()
    # BEGIN explícito: sin esto, si el INSERT de despachos (envuelto en
    # SAVEPOINT por insertar_despacho_con_numero) es la primera escritura de
    # la transacción, sqlite3 no reconoce SAVEPOINT como algo que requiera
    # transacción implícita y el RELEASE SAVEPOINT comitea esa porción por su
    # cuenta — dejando un despacho huérfano si algo falla después. No
    # reproduce en Postgres/psycopg2 (abre transacción en la primera
    # sentencia, sea cual sea), pero toda la verificación local corre contra
    # SQLite, así que el fix va acá de forma explícita para ambos motores.
    cur.execute("BEGIN")
    cur.execute("""
        SELECT h.*, v.id AS vid, t.id AS tid, t.saldo_usable_l,
               t.estado AS tarjeta_estado, s.litros_reservados AS sub_litros,
               cli.nombre AS cliente_nombre
        FROM habilitaciones h
        JOIN vehiculos v ON v.id = h.unidad_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        JOIN clientes cli ON cli.id = h.cliente_id
        LEFT JOIN subinventarios s ON s.id = h.subinventario_id
        WHERE h.id = ?
    """, (hab_id,))
    hab = cur.fetchone()

    if not hab:
        conn.close()
        return jsonify({"error": "Habilitación no encontrada"}), 404
    if hab["estado"] != "aprobada":
        conn.close()
        return jsonify({"error": f"La habilitación no está aprobada (estado: {hab['estado']})"}), 400

    # Verificar que operador_gasolinera solo despacha en su gasolinera asignada
    if session.get("rol") == "operador_gasolinera":
        gid_sesion = session.get("gasolinera_id")
        if not gid_sesion or int(hab["gasolinera_id"]) != int(gid_sesion):
            conn.close()
            return jsonify({"error": "No autorizado: esta habilitación no corresponde a tu gasolinera"}), 403

    # Validar estado de la tarjeta
    if hab["tarjeta_estado"] != "activa":
        conn.close()
        return jsonify({"error": "La tarjeta no está activa"}), 400

    # Validar saldo_usable_l (litros) — única fuente de verdad
    if float(hab["saldo_usable_l"]) < litros - 0.001:
        conn.close()
        return jsonify({"error": f"Saldo insuficiente: {float(hab['saldo_usable_l']):,.2f} L disponible"}), 400

    factor = obtener_factor(cur)
    monto_usd = round(litros * factor, 2)

    hoy_str = date.today().isoformat()

    nuevo_despacho_id, numero_operacion = insertar_despacho_con_numero(
        cur,
        """
            INSERT INTO despachos
                (habilitacion_id, gasolinera_id, tarjeta_id, cliente_id, unidad_id,
                 litros_despachados, fecha_despacho, operario_id, estado, numero_operacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completado', ?)
        """,
        (hab_id, hab["gasolinera_id"], hab["tarjeta_id"], hab["cliente_id"],
         hab["unidad_id"], litros, hoy_str, session.get("user_id")),
        hab["gasolinera_id"], hoy_str,
    )

    foto_url = guardar_adjunto(cur, "despacho", nuevo_despacho_id, "ticket", foto)
    cur.execute("""
        UPDATE despachos SET foto_ticket_url = ? WHERE id = ?
    """, (foto_url, nuevo_despacho_id))

    cur.execute("""
        UPDATE habilitaciones SET estado='despachada', litros_despachados=?,
        updated_at=CURRENT_TIMESTAMP WHERE id=?
    """, (litros, hab_id))

    cur.execute("""
        UPDATE tarjetas
        SET saldo_usable_l = saldo_usable_l - ?,
            saldo_usd = ROUND((saldo_usable_l - ?) * ?, 2),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND saldo_usable_l >= ? - 0.001
    """, (litros, litros, factor, hab["tarjeta_id"], litros))

    if cur.rowcount == 0:
        # Carrera: el saldo cambió entre la validación y el UPDATE. Abortar sin comitear.
        conn.close()
        return jsonify({
            "error": "El saldo de la tarjeta cambió mientras se procesaba el despacho. Intenta de nuevo."
        }), 400

    cur.execute("""
        INSERT INTO movimientos_saldo_fincimex
            (tipo, monto_usd, litros, factor, tarjeta_id, responsable_id, observaciones)
        VALUES ('descuento', ?, ?, ?, ?, ?, ?)
    """, (
        monto_usd, litros, factor, hab["tarjeta_id"],
        session.get("user_id"),
        f"Despacho habilitación #{hab_id} — turno — {litros:,.2f} L × {factor}",
    ))

    if hab["subinventario_id"] and hab["sub_litros"] is not None:
        cur.execute("""
            UPDATE subinventarios
            SET litros_reservados = litros_reservados - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (litros, hab["subinventario_id"]))

    cur.execute("""
        INSERT INTO movimientos (tipo, fecha, gasolinera_id, tarjeta_id, cliente_id,
            vehiculo_id, litros, tipo_combustible, responsable_id, observaciones)
        SELECT 'despacho', ?, h.gasolinera_id, h.tarjeta_id, h.cliente_id,
               h.unidad_id, ?, v.tipo_combustible, ?, ?
        FROM habilitaciones h JOIN vehiculos v ON v.id = h.unidad_id
        WHERE h.id = ?
    """, (hoy_str, litros, session.get("user_id"),
          f"Despacho QR — Habilitación #{hab_id}", hab_id))

    try:
        apartar_remanente_despacho(
            cur, hab, litros, hab_id, nuevo_despacho_id, session.get("user_id")
        )
    except SubinventarioError as e:
        conn.close()
        return jsonify({"error": f"No se pudo apartar el remanente del despacho: {e}"}), 400

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "estado": "despachada", "litros": litros, "numero_operacion": numero_operacion})


# ── Cerrar turno / conciliación ───────────────────────────────────────────────

@turno_bp.route("/cerrar", methods=["POST"])
def cerrar_turno():
    redir = requiere_staff()
    if redir:
        return redirect("/login")

    gasolinera_id = request.form.get("gasolinera_id", "")
    fecha = request.form.get("fecha", "")
    saldo_inicio_str = request.form.get("saldo_fisico_inicio", "0").replace(",", ".")
    saldo_fin_str = request.form.get("saldo_fisico_fin", "0").replace(",", ".")
    observaciones = request.form.get("observaciones", "").strip() or None

    try:
        saldo_inicio = float(saldo_inicio_str)
        saldo_fin = float(saldo_fin_str)
    except ValueError:
        return redirect(f"/turno/?gasolinera_id={gasolinera_id}&fecha={fecha}&access_error=Saldos+inválidos")

    conn = conectar()
    cur = conn.cursor()

    # Total despachado en este turno/gasolinera/fecha
    cur.execute("""
        SELECT COALESCE(SUM(d.litros_despachados), 0) AS total
        FROM despachos d
        JOIN habilitaciones h ON h.id = d.habilitacion_id
        WHERE h.gasolinera_id = ? AND d.fecha_despacho = ? AND d.estado = 'completado'
    """, (gasolinera_id, fecha))
    total_despachado = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS total FROM movimientos
        WHERE gasolinera_id = ? AND fecha = ? AND tipo = 'transferencia_entrada'
    """, (gasolinera_id, fecha))
    total_entrada = cur.fetchone()["total"] or 0

    diferencia = saldo_fin - (saldo_inicio + total_entrada - total_despachado)
    diff_pct = abs(diferencia / saldo_inicio * 100) if saldo_inicio > 0 else 0
    estado = "cerrada" if diff_pct <= 0.5 else "con_alerta"

    cur.execute("""
        INSERT INTO conciliaciones
            (gasolinera_id, fecha, saldo_fisico_inicio_l, saldo_fisico_fin_l,
             total_entrada_l, total_despachado_l, diferencia_l, diferencia_porcentaje,
             estado, responsable_id, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (gasolinera_id, fecha,
          saldo_inicio, saldo_fin, total_entrada, total_despachado,
          diferencia, diff_pct, estado, session.get("user_id"), observaciones))

    conn.commit()
    conn.close()
    return redirect(f"/turno/?gasolinera_id={gasolinera_id}&fecha={fecha}&ok=1")


# ── Escaneo QR (operario) ─────────────────────────────────────────────────────

@turno_bp.route("/escanear")
def escanear():
    redir = _requiere_operario_gas()
    if redir:
        return redir
    return render_template("turno/escanear.html")


@turno_bp.route("/api/reserva-info/<token>")
def api_reserva_info(token):
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.estado, r.tipo_combustible, r.litros_solicitados,
               r.precio_usd_por_litro, r.precio_total_usd,
               r.descripcion_vehiculo, r.observaciones,
               g.nombre AS gasolinera_nombre,
               u.nombre AS cliente_nombre, u.email AS cliente_email
        FROM reservas_tienda r
        JOIN gasolineras g ON g.id = r.gasolinera_id
        JOIN usuarios u ON u.id = r.usuario_id
        WHERE r.qr_token = ?
    """, (token,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Token no encontrado"}), 404

    return jsonify({
        "id": row["id"],
        "estado": row["estado"],
        "tipo_combustible": row["tipo_combustible"],
        "litros": float(row["litros_solicitados"]),
        "precio_unitario": float(row["precio_usd_por_litro"]),
        "precio_total": float(row["precio_total_usd"]),
        "vehiculo": row["descripcion_vehiculo"] or "—",
        "observaciones": row["observaciones"] or "—",
        "gasolinera": row["gasolinera_nombre"],
        "cliente": row["cliente_nombre"],
        "cliente_email": row["cliente_email"],
    })


@turno_bp.route("/api/reserva-info-por-numero/<int:reserva_id>")
def api_reserva_info_por_numero(reserva_id):
    """Igual que api_reserva_info, pero busca por el número (id) de la reserva
    en vez de por el token del QR — para despachar sin QR/cámara disponible.
    Devuelve además el token real, para reutilizar el mismo flujo de completar()."""
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.estado, r.tipo_combustible, r.litros_solicitados,
               r.precio_usd_por_litro, r.precio_total_usd,
               r.descripcion_vehiculo, r.observaciones, r.qr_token,
               g.nombre AS gasolinera_nombre,
               u.nombre AS cliente_nombre, u.email AS cliente_email
        FROM reservas_tienda r
        JOIN gasolineras g ON g.id = r.gasolinera_id
        JOIN usuarios u ON u.id = r.usuario_id
        WHERE r.id = ?
    """, (reserva_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "No existe una reserva con ese número"}), 404

    return jsonify({
        "id": row["id"],
        "token": row["qr_token"],
        "estado": row["estado"],
        "tipo_combustible": row["tipo_combustible"],
        "litros": float(row["litros_solicitados"]),
        "precio_unitario": float(row["precio_usd_por_litro"]),
        "precio_total": float(row["precio_total_usd"]),
        "vehiculo": row["descripcion_vehiculo"] or "—",
        "observaciones": row["observaciones"] or "—",
        "gasolinera": row["gasolinera_nombre"],
        "cliente": row["cliente_nombre"],
        "cliente_email": row["cliente_email"],
    })


@turno_bp.route("/api/habilitacion-info/<int:hab_id>")
def api_habilitacion_info(hab_id):
    """Consulta de solo lectura de una habilitación por su número — para
    despachar sin QR/cámara disponible. El despacho en sí sigue haciéndose
    con api_despachar(hab_id), sin cambios."""
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT h.id, h.estado, h.litros_autorizados, h.gasolinera_id,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa, v.tipo_combustible,
               ch.nombre AS chofer_nombre,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial
        FROM habilitaciones h
        JOIN clientes cli ON cli.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = h.gasolinera_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        WHERE h.id = ?
    """, (hab_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "No existe una habilitación con ese número"}), 404

    return jsonify({
        "id": row["id"],
        "estado": row["estado"],
        "litros_autorizados": float(row["litros_autorizados"]),
        "gasolinera_id": row["gasolinera_id"],
        "gasolinera": row["gasolinera_nombre"],
        "cliente": row["cliente_nombre"],
        "unidad": row["unidad_chapa"],
        "chofer": row["chofer_nombre"] or "—",
        "tipo_combustible": row["tipo_combustible"],
        "tarjeta": row["tarjeta_parcial"],
    })


@turno_bp.route("/api/reserva-completar/<token>", methods=["POST"])
def api_reserva_completar(token):
    redir = requiere_staff()
    if redir:
        return jsonify({"error": "No autorizado"}), 401
    if session.get("rol") not in ROLES_OPERARIO_GAS:
        return jsonify({"error": "Sin permiso"}), 403

    foto = request.files.get("foto_ticket")
    if foto and foto.filename and not foto_valida(foto):
        return jsonify({"error": "Formato de foto no válido. Use JPG, PNG o WEBP."}), 400

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.id, r.estado, r.tarjeta_id, r.litros_solicitados, r.gasolinera_id,
               r.tipo_combustible, u.id AS cliente_id, u.nombre AS cliente_nombre,
               u.email AS cliente_email, g.nombre AS gasolinera_nombre
        FROM reservas_tienda r
        JOIN usuarios u ON u.id = r.usuario_id
        JOIN gasolineras g ON g.id = r.gasolinera_id
        WHERE r.qr_token = ?
    """, (token,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Token no encontrado"}), 404
    if row["estado"] != "aprobada":
        conn.close()
        return jsonify({"error": f"La reserva no está aprobada (estado: {row['estado']})"}), 400

    # Verificar que operador_gasolinera solo completa reservas de su gasolinera
    if session.get("rol") == "operador_gasolinera":
        gid_sesion = session.get("gasolinera_id")
        if not gid_sesion or int(row["gasolinera_id"]) != int(gid_sesion):
            conn.close()
            return jsonify({"error": "No autorizado: esta reserva no corresponde a tu gasolinera"}), 403

    litros = float(row["litros_solicitados"])

    # Si hay tarjeta asignada: validar y descontar saldo_usable_l (bloqueo duro, única fuente de verdad)
    if row["tarjeta_id"]:
        factor = obtener_factor(cur)
        monto_usd = round(litros * factor, 2)

        cur.execute("SELECT saldo_usable_l, estado FROM tarjetas WHERE id=?", (row["tarjeta_id"],))
        t = cur.fetchone()
        if not t:
            conn.close()
            return jsonify({"error": "Tarjeta asignada no encontrada"}), 400
        if t["estado"] != "activa":
            conn.close()
            return jsonify({"error": "La tarjeta no está activa"}), 400
        if float(t["saldo_usable_l"]) < litros - 0.001:
            detalle = (
                f"Disponible: {float(t['saldo_usable_l']):,.2f} L "
                f"(≈ ${calcular_usd_desde_litros(t['saldo_usable_l'], factor):,.2f} USD), "
                f"requerido: {litros:,.2f} L (≈ ${monto_usd:,.2f} USD)."
            )
            conn.close()
            try:
                mailer.staff_sin_cobertura_saldo(
                    row["gasolinera_nombre"], row["tipo_combustible"], detalle
                )
            except Exception:
                logger.error("Error notificando staff de saldo insuficiente (tarjeta #%s)",
                             row["tarjeta_id"], exc_info=True)
            return jsonify({
                "error": f"Saldo insuficiente. {detalle}"
            }), 400

    foto_ticket_url = guardar_adjunto(cur, "reserva_tienda", row["id"], "ticket", foto)

    cur.execute("""
        UPDATE reservas_tienda SET estado='completada', foto_ticket_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
    """, (foto_ticket_url, row["id"]))

    if row["tarjeta_id"]:
        cur.execute("""
            UPDATE tarjetas
            SET saldo_usable_l = saldo_usable_l - ?,
                saldo_usd = ROUND((saldo_usable_l - ?) * ?, 2),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND saldo_usable_l >= ? - 0.001
        """, (litros, litros, factor, row["tarjeta_id"], litros))

        if cur.rowcount == 0:
            # Carrera: el saldo cambió entre la validación y el UPDATE. Abortar sin comitear.
            conn.close()
            return jsonify({
                "error": "El saldo de la tarjeta cambió mientras se procesaba el despacho. Intenta de nuevo."
            }), 400

        cur.execute("""
            INSERT INTO movimientos_saldo_fincimex
                (tipo, monto_usd, litros, factor, tarjeta_id, responsable_id, observaciones)
            VALUES ('descuento', ?, ?, ?, ?, ?, ?)
        """, (
            monto_usd, litros, factor, row["tarjeta_id"],
            session.get("user_id"),
            f"Despacho tienda reserva #{row['id']} — QR — {litros:,.2f} L × {factor}",
        ))

    cur.execute("""
        INSERT INTO movimientos
            (tipo, fecha, gasolinera_id, tarjeta_id, cliente_id, litros, tipo_combustible, responsable_id, observaciones)
        VALUES ('despacho', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        date.today().isoformat(), row["gasolinera_id"], row["tarjeta_id"], row["cliente_id"],
        litros, row["tipo_combustible"], session.get("user_id"),
        f"Despacho QR Tienda — Reserva #{row['id']}",
    ))

    conn.commit()
    conn.close()

    try:
        mailer.despacho_completado(
            row["cliente_nombre"], row["cliente_email"], row["cliente_id"],
            row["gasolinera_nombre"], row["tipo_combustible"], litros,
        )
    except Exception:
        logger.error("Error notificando despacho completado (reserva #%s)", row["id"], exc_info=True)

    return jsonify({"ok": True})
