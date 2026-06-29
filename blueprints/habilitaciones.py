from datetime import date

from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import (
    TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM,
    ESTADOS_HABILITACION, ESTADOS_HABILITACION_LABELS,
)
from utils.auth import requiere_login

habilitaciones_bp = Blueprint("habilitaciones", __name__, url_prefix="/habilitaciones")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


# ── Listado ───────────────────────────────────────────────────────────────────

@habilitaciones_bp.route("/")
def listado():
    redir = requiere_login()
    if redir:
        return redir

    filtro_cliente = request.args.get("cliente_id", "").strip()
    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()

    condiciones = []
    params = []

    if filtro_cliente:
        condiciones.append("h.cliente_id = ?")
        params.append(filtro_cliente)
    if filtro_gasolinera:
        condiciones.append("h.gasolinera_id = ?")
        params.append(filtro_gasolinera)
    if filtro_estado:
        condiciones.append("h.estado = ?")
        params.append(filtro_estado)
    if filtro_desde:
        condiciones.append("h.fecha_habilitacion >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        condiciones.append("h.fecha_habilitacion <= ?")
        params.append(filtro_hasta)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT h.id, h.litros_autorizados, h.litros_despachados,
               h.fecha_habilitacion, h.fecha_vencimiento, h.estado,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa, v.tipo_combustible,
               ch.nombre AS chofer_nombre,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               u_c.nombre AS creado_por_nombre
        FROM habilitaciones h
        JOIN clientes cli ON cli.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = h.gasolinera_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        JOIN usuarios u_c ON u_c.id = h.creado_por
        {where}
        ORDER BY h.id DESC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    conn.close()

    return render_template(
        "habilitaciones/listado.html",
        lista=lista,
        clientes=clientes,
        gasolineras=gasolineras,
        filtro_cliente=filtro_cliente,
        filtro_gasolinera=filtro_gasolinera,
        filtro_estado=filtro_estado,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        estados_habilitacion=ESTADOS_HABILITACION,
        estado_labels=ESTADOS_HABILITACION_LABELS,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


# ── Detalle ───────────────────────────────────────────────────────────────────

@habilitaciones_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT h.*,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa, v.tipo_combustible, v.marca, v.modelo,
               ch.nombre AS chofer_nombre, ch.ci AS chofer_ci,
               ch.licencia_numero, ch.licencia_vencimiento,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               t.saldo_usable_l AS tarjeta_saldo,
               s.nombre AS subinventario_nombre,
               u_c.nombre AS creado_por_nombre,
               u_a.nombre AS aprobado_por_nombre
        FROM habilitaciones h
        JOIN clientes cli ON cli.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = h.gasolinera_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        LEFT JOIN subinventarios s ON s.id = h.subinventario_id
        JOIN usuarios u_c ON u_c.id = h.creado_por
        LEFT JOIN usuarios u_a ON u_a.id = h.aprobado_por
        WHERE h.id = ?
    """, (id,))
    hab = cur.fetchone()

    if not hab:
        conn.close()
        return redirect("/habilitaciones")

    despacho = None
    cur.execute("""
        SELECT d.*, u_op.nombre AS operario_nombre
        FROM despachos d
        JOIN usuarios u_op ON u_op.id = d.operario_id
        WHERE d.habilitacion_id = ?
    """, (id,))
    despacho = cur.fetchone()
    conn.close()

    return render_template(
        "habilitaciones/detalle.html",
        hab=hab,
        despacho=despacho,
        estado_labels=ESTADOS_HABILITACION_LABELS,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
    )


# ── Crear ─────────────────────────────────────────────────────────────────────

@habilitaciones_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/habilitaciones?access_error=Solo+Admin+y+PM+pueden+crear+habilitaciones")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, codigo FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    cur.execute("""
        SELECT v.id, v.chapa, v.cliente_id, v.tipo_combustible, v.estado,
               ch.nombre AS chofer_nombre, ch.licencia_vencimiento
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        WHERE v.estado = 'activo'
        ORDER BY v.chapa ASC
    """)
    unidades = cur.fetchall()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    cur.execute("""
        SELECT t.id, t.numero_parcial, t.gasolinera_id, t.tipo_combustible,
               t.saldo_usable_l, t.estado
        FROM tarjetas t
        WHERE t.estado = 'activa'
        ORDER BY t.numero_parcial ASC
    """)
    tarjetas = cur.fetchall()
    cur.execute("""
        SELECT s.id, s.nombre, s.gasolinera_id, s.litros_reservados, s.activo
        FROM subinventarios s
        WHERE s.activo = 1
        ORDER BY s.nombre ASC
    """)
    subinventarios = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id", "").strip()
        unidad_id = request.form.get("unidad_id", "").strip()
        gasolinera_id = request.form.get("gasolinera_id", "").strip()
        tarjeta_id = request.form.get("tarjeta_id", "").strip()
        subinventario_id = request.form.get("subinventario_id", "").strip() or None
        litros_str = request.form.get("litros_autorizados", "0").strip()
        fecha_hab = request.form.get("fecha_habilitacion", "").strip()
        fecha_venc = request.form.get("fecha_vencimiento", "").strip() or None
        observaciones = request.form.get("observaciones", "").strip()

        if not cliente_id:
            error = "Debe seleccionar un cliente."
        elif not unidad_id:
            error = "Debe seleccionar una unidad."
        elif not gasolinera_id:
            error = "Debe seleccionar una gasolinera."
        elif not tarjeta_id:
            error = "Debe seleccionar una tarjeta."
        elif not fecha_hab:
            error = "La fecha de habilitación es obligatoria."
        else:
            try:
                litros = float(litros_str.replace(",", "."))
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."
            if not error and litros <= 0:
                error = "Los litros autorizados deben ser mayores a cero."
            if not error:
                conn2 = conectar()
                cur2 = conn2.cursor()
                cur2.execute("SELECT valor FROM configuracion WHERE clave = 'compra_minima_litros'")
                row_min = cur2.fetchone()
                conn2.close()
                if row_min:
                    minimo = float(row_min["valor"])
                    if litros < minimo:
                        error = f"El mínimo de litros por habilitación es {minimo:,.0f} L (configurado en el sistema)."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO habilitaciones
                    (cliente_id, unidad_id, gasolinera_id, tarjeta_id, subinventario_id,
                     litros_autorizados, fecha_habilitacion, fecha_vencimiento,
                     estado, observaciones, creado_por)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
            """, (cliente_id, unidad_id, gasolinera_id, tarjeta_id, subinventario_id,
                  litros, fecha_hab, fecha_venc, observaciones or None, session.get("user_id")))
            nuevo_id = cur.lastrowid
            conn.commit()
            conn.close()
            return redirect(f"/habilitaciones/{nuevo_id}?ok=1")

    return render_template(
        "habilitaciones/crear.html",
        error=error,
        clientes=clientes,
        unidades=unidades,
        gasolineras=gasolineras,
        tarjetas=tarjetas,
        subinventarios=subinventarios,
        hoy=date.today().isoformat(),
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        cliente_pre=request.args.get("cliente_id", ""),
    )


# ── Aprobar ───────────────────────────────────────────────────────────────────

@habilitaciones_bp.route("/<int:id>/aprobar", methods=["POST"])
def aprobar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/habilitaciones/{id}?access_error=Solo+Admin+y+PM+pueden+aprobar")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT h.*,
               v.estado AS unidad_estado, v.chofer_id,
               ch.licencia_vencimiento,
               t.estado AS tarjeta_estado, t.saldo_usable_l,
               s.litros_reservados AS sub_litros
        FROM habilitaciones h
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        LEFT JOIN subinventarios s ON s.id = h.subinventario_id
        WHERE h.id = ?
    """, (id,))
    hab = cur.fetchone()

    if not hab:
        conn.close()
        return redirect("/habilitaciones?access_error=Habilitación+no+encontrada")

    if hab["estado"] != "pendiente":
        conn.close()
        return redirect(f"/habilitaciones/{id}?access_error=Solo+se+pueden+aprobar+habilitaciones+pendientes")

    error = None
    litros = float(hab["litros_autorizados"])

    if hab["unidad_estado"] != "activo":
        error = "La unidad no está activa."
    elif hab["chofer_id"] and hab["licencia_vencimiento"] and hab["licencia_vencimiento"] < date.today().isoformat():
        error = f"El chofer tiene la licencia vencida ({hab['licencia_vencimiento']})."
    elif hab["tarjeta_estado"] != "activa":
        error = "La tarjeta no está activa."
    elif float(hab["saldo_usable_l"]) < litros - 0.001:
        error = (
            f"Saldo insuficiente en la tarjeta. Disponible: {float(hab['saldo_usable_l']):,.2f} L, "
            f"requerido: {litros:,.2f} L."
        )
    elif hab["subinventario_id"] and hab["sub_litros"] is not None:
        if float(hab["sub_litros"]) < litros - 0.001:
            error = (
                f"El subinventario tiene {float(hab['sub_litros']):,.2f} L reservados, "
                f"insuficiente para {litros:,.2f} L."
            )

    if error:
        conn.close()
        return redirect(f"/habilitaciones/{id}?access_error={error.replace(' ', '+')}")

    cur.execute("""
        UPDATE habilitaciones
        SET estado = 'aprobada', aprobado_por = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (session.get("user_id"), id))
    conn.commit()
    conn.close()
    return redirect(f"/habilitaciones/{id}?ok=1")


# ── Cancelar ──────────────────────────────────────────────────────────────────

@habilitaciones_bp.route("/<int:id>/cancelar", methods=["POST"])
def cancelar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/habilitaciones/{id}?access_error=Solo+Admin+y+PM+pueden+cancelar")

    observaciones = request.form.get("observaciones", "").strip()
    if not observaciones:
        return redirect(f"/habilitaciones/{id}?access_error=La+observación+es+obligatoria+para+cancelar")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM habilitaciones WHERE id = ?", (id,))
    row = cur.fetchone()

    if not row or row["estado"] not in ("pendiente", "aprobada"):
        conn.close()
        return redirect(f"/habilitaciones/{id}?access_error=No+se+puede+cancelar+en+estado+actual")

    cur.execute("""
        UPDATE habilitaciones
        SET estado = 'cancelada', observaciones = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (observaciones, id))
    conn.commit()
    conn.close()
    return redirect(f"/habilitaciones/{id}?ok=1")
