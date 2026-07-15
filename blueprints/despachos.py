from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, session

from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE_LABELS, ESTADOS_HABILITACION_LABELS
from utils.auth import requiere_login, requiere_staff
from utils.adjuntos import foto_valida, guardar_adjunto
from utils.despachos import insertar_despacho_con_numero
from utils.tarjetas import obtener_factor, calcular_usd_desde_litros
from utils.subinventarios import apartar_remanente_despacho, SubinventarioError

despachos_bp = Blueprint("despachos", __name__, url_prefix="/despachos")


# ── Listado ───────────────────────────────────────────────────────────────────

@despachos_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_cliente = request.args.get("cliente_id", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()
    filtro_estado = request.args.get("estado", "").strip()

    condiciones = []
    params = []

    # Para operador_gasolinera: restringir siempre a su gasolinera asignada
    if session.get("rol") == "operador_gasolinera":
        condiciones.append("d.gasolinera_id = ?")
        params.append(session.get("gasolinera_id"))
    elif filtro_gasolinera:
        condiciones.append("d.gasolinera_id = ?")
        params.append(filtro_gasolinera)
    if filtro_cliente:
        condiciones.append("d.cliente_id = ?")
        params.append(filtro_cliente)
    if filtro_desde:
        condiciones.append("d.fecha_despacho >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        condiciones.append("d.fecha_despacho < ?")
        params.append(filtro_hasta + "T23:59:59" if "T" not in filtro_hasta else filtro_hasta)
    if filtro_estado:
        condiciones.append("d.estado = ?")
        params.append(filtro_estado)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT d.id, d.litros_despachados, d.fecha_despacho, d.estado,
               d.foto_ticket_url, d.odometro_km, d.numero_operacion,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa,
               ch.nombre AS chofer_nombre,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               h.litros_autorizados,
               u_op.nombre AS operario_nombre
        FROM despachos d
        JOIN habilitaciones h ON h.id = d.habilitacion_id
        JOIN clientes cli ON cli.id = d.cliente_id
        JOIN vehiculos v ON v.id = d.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = d.gasolinera_id
        JOIN tarjetas t ON t.id = d.tarjeta_id
        JOIN usuarios u_op ON u_op.id = d.operario_id
        {where}
        ORDER BY d.id DESC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    cur.execute("SELECT id, nombre FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()

    # Reservas de tienda aprobadas pendientes de despachar
    # operador_gasolinera: solo las de su gasolinera. admin/pm/puesto_de_mando: todas.
    if session.get("rol") == "operador_gasolinera":
        cur.execute("""
            SELECT r.id, r.litros_solicitados, r.tipo_combustible,
                   r.descripcion_vehiculo, r.created_at, r.qr_token,
                   g.nombre AS gasolinera_nombre,
                   u.nombre AS cliente_nombre
            FROM reservas_tienda r
            JOIN gasolineras g ON g.id = r.gasolinera_id
            JOIN usuarios u ON u.id = r.usuario_id
            WHERE r.estado = 'aprobada' AND r.gasolinera_id = ?
            ORDER BY r.created_at ASC
        """, (session.get("gasolinera_id"),))
    else:
        cur.execute("""
            SELECT r.id, r.litros_solicitados, r.tipo_combustible,
                   r.descripcion_vehiculo, r.created_at, r.qr_token,
                   g.nombre AS gasolinera_nombre,
                   u.nombre AS cliente_nombre
            FROM reservas_tienda r
            JOIN gasolineras g ON g.id = r.gasolinera_id
            JOIN usuarios u ON u.id = r.usuario_id
            WHERE r.estado = 'aprobada'
            ORDER BY r.created_at ASC
        """)
    reservas_tienda_pendientes = cur.fetchall()

    conn.close()

    return render_template(
        "despachos/listado.html",
        lista=lista,
        gasolineras=gasolineras,
        clientes=clientes,
        filtro_gasolinera=filtro_gasolinera,
        filtro_cliente=filtro_cliente,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        filtro_estado=filtro_estado,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        reservas_tienda_pendientes=reservas_tienda_pendientes,
    )


# ── Detalle ───────────────────────────────────────────────────────────────────

@despachos_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.*,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa, v.tipo_combustible, v.marca, v.modelo,
               ch.nombre AS chofer_nombre, ch.ci AS chofer_ci,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               h.litros_autorizados, h.fecha_habilitacion,
               u_op.nombre AS operario_nombre
        FROM despachos d
        JOIN habilitaciones h ON h.id = d.habilitacion_id
        JOIN clientes cli ON cli.id = d.cliente_id
        JOIN vehiculos v ON v.id = d.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = d.gasolinera_id
        JOIN tarjetas t ON t.id = d.tarjeta_id
        JOIN usuarios u_op ON u_op.id = d.operario_id
        WHERE d.id = ?
    """, (id,))
    despacho = cur.fetchone()
    conn.close()

    if not despacho:
        return redirect("/despachos")

    return render_template(
        "despachos/detalle.html",
        despacho=despacho,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


# ── Subir foto diferida ──────────────────────────────────────────────────────

@despachos_bp.route("/<int:id>/subir-foto", methods=["POST"])
def subir_foto(id):
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, gasolinera_id, foto_ticket_url FROM despachos WHERE id = ?", (id,))
    despacho = cur.fetchone()

    if not despacho:
        conn.close()
        return redirect("/despachos")

    if session.get("rol") == "operador_gasolinera":
        gid_sesion = session.get("gasolinera_id")
        if not gid_sesion or int(despacho["gasolinera_id"]) != int(gid_sesion):
            conn.close()
            return redirect(f"/despachos/{id}?access_error=No+autorizado:+este+despacho+no+corresponde+a+tu+gasolinera")

    foto_ticket = request.files.get("foto_ticket")
    if not foto_ticket or not foto_ticket.filename:
        conn.close()
        return redirect(f"/despachos/{id}?access_error=Debe+seleccionar+una+foto")
    if not foto_valida(foto_ticket):
        conn.close()
        return redirect(f"/despachos/{id}?access_error=Formato+de+foto+no+válido.+Use+JPG,+PNG+o+WEBP")

    foto_ticket_url = guardar_adjunto(cur, "despacho", id, "ticket", foto_ticket)
    cur.execute("UPDATE despachos SET foto_ticket_url = ? WHERE id = ?", (foto_ticket_url, id))
    conn.commit()
    conn.close()
    return redirect(f"/despachos/{id}?ok=1")


# ── Crear ─────────────────────────────────────────────────────────────────────

@despachos_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    _habs_cond = ""
    _habs_params = []
    if session.get("rol") == "operador_gasolinera":
        _habs_cond = "AND h.gasolinera_id = ?"
        _habs_params.append(session.get("gasolinera_id"))

    cur.execute(f"""
        SELECT h.id, h.litros_autorizados, h.tarjeta_id, h.subinventario_id,
               h.cliente_id, h.unidad_id, h.gasolinera_id,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa,
               ch.nombre AS chofer_nombre,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial
        FROM habilitaciones h
        JOIN clientes cli ON cli.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = h.gasolinera_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        WHERE h.estado = 'aprobada'
        AND NOT EXISTS (
            SELECT 1 FROM despachos d
            WHERE d.habilitacion_id = h.id AND d.estado = 'completado'
        )
        {_habs_cond}
        ORDER BY h.id DESC
    """, _habs_params)
    habilitaciones = cur.fetchall()
    conn.close()

    error = None
    hab_pre = request.args.get("habilitacion_id", "").strip()

    if request.method == "POST":
        habilitacion_id = request.form.get("habilitacion_id", "").strip()
        litros_str = request.form.get("litros_despachados", "0").strip()
        odometro_str = request.form.get("odometro_km", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        foto_ticket = request.files.get("foto_ticket")
        foto_vehiculo = request.files.get("foto_vehiculo")
        foto_odometro = request.files.get("foto_odometro")

        if not habilitacion_id:
            error = "Debe seleccionar una habilitación aprobada."
        elif foto_ticket and foto_ticket.filename and not foto_valida(foto_ticket):
            error = "Formato de foto no válido. Use JPG, PNG o WEBP."
        elif foto_vehiculo and foto_vehiculo.filename and not foto_valida(foto_vehiculo):
            error = "Formato de foto de vehículo no válido. Use JPG, PNG o WEBP."
        elif foto_odometro and foto_odometro.filename and not foto_valida(foto_odometro):
            error = "Formato de foto de odómetro no válido. Use JPG, PNG o WEBP."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."
            if not error and litros <= 0:
                error = "Los litros despachados deben ser mayores a cero."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                SELECT h.*,
                       t.saldo_usable_l, t.estado AS tarjeta_estado,
                       s.litros_reservados AS sub_litros,
                       cli.nombre AS cliente_nombre
                FROM habilitaciones h
                JOIN tarjetas t ON t.id = h.tarjeta_id
                JOIN clientes cli ON cli.id = h.cliente_id
                LEFT JOIN subinventarios s ON s.id = h.subinventario_id
                WHERE h.id = ? AND h.estado = 'aprobada'
            """, (habilitacion_id,))
            hab = cur.fetchone()

            factor = obtener_factor(cur)
            monto_usd = round(litros * factor, 2)

            if not hab:
                error = "La habilitación no está disponible para despacho."
                conn.close()
            elif hab["tarjeta_estado"] != "activa":
                error = "La tarjeta no está activa."
                conn.close()
            elif float(hab["saldo_usable_l"]) < litros - 0.001:
                error = (
                    f"Saldo insuficiente en la tarjeta. Disponible: "
                    f"{float(hab['saldo_usable_l']):,.2f} L "
                    f"(≈ ${calcular_usd_desde_litros(hab['saldo_usable_l'], factor):,.2f} USD), "
                    f"solicitado: {litros:,.2f} L."
                )
                conn.close()
            if not error:
                try:
                    odometro_km = int(odometro_str) if odometro_str else None
                except ValueError:
                    odometro_km = None

                fecha_despacho = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # saldo_usable_l es la única fuente de verdad para el bloqueo;
                # saldo_usd se recalcula como espejo (a partir del valor ANTERIOR
                # de saldo_usable_l) solo por consistencia, hasta el DROP futuro.
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
                    error = "El saldo de la tarjeta cambió mientras se procesaba el despacho. Intenta de nuevo."
                else:
                    cur.execute("""
                        INSERT INTO movimientos_saldo_fincimex
                            (tipo, monto_usd, litros, factor, tarjeta_id, responsable_id, observaciones)
                        VALUES ('descuento', ?, ?, ?, ?, ?, ?)
                    """, (
                        monto_usd, litros, factor, hab["tarjeta_id"],
                        session.get("user_id"),
                        f"Despacho habilitación #{habilitacion_id} — {litros:,.2f} L × {factor}",
                    ))

                    if hab["subinventario_id"] and hab["sub_litros"] is not None:
                        cur.execute("""
                            UPDATE subinventarios
                            SET litros_reservados = litros_reservados - ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        """, (litros, hab["subinventario_id"]))

                    cur.execute("""
                        UPDATE habilitaciones
                        SET litros_despachados = ?, estado = 'despachada',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (litros, habilitacion_id))

                    nuevo_id, numero_operacion = insertar_despacho_con_numero(
                        cur,
                        """
                            INSERT INTO despachos
                                (habilitacion_id, gasolinera_id, tarjeta_id, cliente_id, unidad_id,
                                 litros_despachados, odometro_km, observaciones, fecha_despacho,
                                 operario_id, estado, numero_operacion)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completado', ?)
                        """,
                        (habilitacion_id, hab["gasolinera_id"], hab["tarjeta_id"],
                         hab["cliente_id"], hab["unidad_id"], litros,
                         odometro_km, observaciones or None, fecha_despacho,
                         session.get("user_id")),
                        hab["gasolinera_id"], fecha_despacho,
                    )

                    foto_ticket_url = guardar_adjunto(cur, "despacho", nuevo_id, "ticket", foto_ticket)
                    foto_vehiculo_url = guardar_adjunto(cur, "despacho", nuevo_id, "vehiculo", foto_vehiculo)
                    foto_odometro_url = guardar_adjunto(cur, "despacho", nuevo_id, "odometro", foto_odometro)
                    cur.execute("""
                        UPDATE despachos
                        SET foto_ticket_url = ?, foto_vehiculo_url = ?, foto_odometro_url = ?
                        WHERE id = ?
                    """, (foto_ticket_url, foto_vehiculo_url, foto_odometro_url, nuevo_id))

                    cur.execute("""
                        INSERT INTO movimientos
                            (tipo, fecha, gasolinera_id, tarjeta_id, cliente_id, vehiculo_id,
                             litros, tipo_combustible, responsable_id, observaciones)
                        VALUES ('despacho', ?, ?, ?, ?, ?, ?, (
                            SELECT tipo_combustible FROM tarjetas WHERE id = ?
                        ), ?, ?)
                    """, (fecha_despacho, hab["gasolinera_id"], hab["tarjeta_id"],
                          hab["cliente_id"], hab["unidad_id"], litros, hab["tarjeta_id"],
                          session.get("user_id"),
                          f"Despacho #{nuevo_id} — Habilitación #{habilitacion_id}"))

                    try:
                        apartar_remanente_despacho(
                            cur, hab, litros, habilitacion_id, nuevo_id, session.get("user_id")
                        )
                    except SubinventarioError as e:
                        conn.close()
                        error = f"No se pudo apartar el remanente del despacho: {e}"
                    else:
                        conn.commit()
                        conn.close()
                        return redirect(f"/despachos/{nuevo_id}?ok=1")

    return render_template(
        "despachos/crear.html",
        error=error,
        habilitaciones=habilitaciones,
        hab_pre=hab_pre,
        hoy=date.today().isoformat(),
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        estado_labels=ESTADOS_HABILITACION_LABELS,
    )
