from datetime import date

from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import (
    TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM,
    ESTADOS_HABILITACION, ESTADOS_HABILITACION_LABELS,
)
from utils.auth import requiere_login, requiere_staff
from utils.subinventarios import crear_subinventario, ajustar_reserva, SubinventarioError
from utils.tarjetas import obtener_factor, calcular_usd_desde_litros

habilitaciones_bp = Blueprint("habilitaciones", __name__, url_prefix="/habilitaciones")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


def _validar_estructural(cur, cliente_id, unidad_id, gasolinera_id, tarjeta_id,
                          subinventario_id, litros, verificar_sub_litros=True):
    """Valida las incongruencias ESTRUCTURALES entre cliente/unidad/gasolinera/tarjeta/
    subinventario — datos fijos que no cambian entre crear y aprobar, por lo que se pueden
    (y deben) bloquear ya en el momento de crear o editar.

    Devuelve (error, tarjeta_check, unidad_check). tarjeta_check/unidad_check se devuelven
    para que el llamador pueda reutilizarlos al calcular avisos de ESTADO sin otra consulta.
    """
    cur.execute("""
        SELECT gasolinera_id, tipo_combustible, estado, saldo_usable_l
        FROM tarjetas WHERE id = ?
    """, (tarjeta_id,))
    tarjeta_check = cur.fetchone()
    cur.execute("""
        SELECT v.tipo_combustible, v.cliente_id, v.estado, v.chofer_id, ch.licencia_vencimiento
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        WHERE v.id = ?
    """, (unidad_id,))
    unidad_check = cur.fetchone()
    sub_check = None
    if subinventario_id:
        cur.execute(
            "SELECT gasolinera_id, litros_reservados FROM subinventarios WHERE id = ? AND activo = 1",
            (subinventario_id,),
        )
        sub_check = cur.fetchone()

    error = None
    if not tarjeta_check or not unidad_check:
        error = "La tarjeta o la unidad seleccionada no es válida."
    elif str(tarjeta_check["gasolinera_id"]) != str(gasolinera_id):
        error = "La tarjeta seleccionada no corresponde a la gasolinera elegida."
    elif tarjeta_check["tipo_combustible"] != unidad_check["tipo_combustible"]:
        error = "La tarjeta seleccionada no corresponde al tipo de combustible de la unidad."
    elif str(unidad_check["cliente_id"]) != str(cliente_id):
        error = "La unidad seleccionada no pertenece al cliente elegido."
    elif subinventario_id and not sub_check:
        error = "El subinventario seleccionado no es válido."
    elif subinventario_id and str(sub_check["gasolinera_id"]) != str(gasolinera_id):
        error = "El subinventario seleccionado no pertenece a la gasolinera elegida."
    elif subinventario_id and verificar_sub_litros and float(sub_check["litros_reservados"]) < litros - 0.001:
        error = (
            f"El subinventario tiene {float(sub_check['litros_reservados']):,.2f} L reservados, "
            f"insuficiente para {litros:,.2f} L."
        )
    return error, tarjeta_check, unidad_check


def _calcular_avisos_estado(unidad_estado, chofer_id, licencia_vencimiento,
                             tarjeta_estado, saldo_usable_l, litros_autorizados):
    """Incongruencias de ESTADO: pueden cambiar entre crear y aprobar (saldo se consume,
    tarjeta se bloquea, licencia vence), así que nunca se bloquean acá — solo se avisan,
    para que el PM sepa qué regularizar antes de aprobar."""
    avisos = []
    if unidad_estado != "activo":
        avisos.append("La unidad no está activa.")
    if chofer_id and licencia_vencimiento and licencia_vencimiento < date.today().isoformat():
        avisos.append(f"El chofer tiene la licencia vencida ({licencia_vencimiento}).")
    if tarjeta_estado != "activa":
        avisos.append("La tarjeta no está activa.")
    if float(saldo_usable_l) < float(litros_autorizados) - 0.001:
        avisos.append(
            f"Saldo insuficiente en la tarjeta. Disponible: {float(saldo_usable_l):,.2f} L, "
            f"requerido: {float(litros_autorizados):,.2f} L."
        )
    return avisos


# ── Listado ───────────────────────────────────────────────────────────────────

@habilitaciones_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    filtro_cliente = request.args.get("cliente_id", "").strip()
    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()

    condiciones = []
    params = []

    # Para operador_gasolinera: restringir siempre a su gasolinera asignada
    if session.get("rol") == "operador_gasolinera":
        condiciones.append("h.gasolinera_id = ?")
        params.append(session.get("gasolinera_id"))
    elif filtro_gasolinera:
        condiciones.append("h.gasolinera_id = ?")
        params.append(filtro_gasolinera)

    if filtro_cliente:
        condiciones.append("h.cliente_id = ?")
        params.append(filtro_cliente)
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
               h.fecha_habilitacion, h.fecha_vencimiento, h.estado, h.created_at,
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
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT h.*,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa, v.tipo_combustible, v.marca, v.modelo,
               v.estado AS unidad_estado, v.chofer_id,
               ch.nombre AS chofer_nombre, ch.ci AS chofer_ci,
               ch.licencia_numero, ch.licencia_vencimiento,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               t.saldo_usable_l AS tarjeta_saldo,
               t.estado AS tarjeta_estado,
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

    avisos = []
    if hab["estado"] in ("pendiente", "en_reserva"):
        avisos = _calcular_avisos_estado(
            hab["unidad_estado"], hab["chofer_id"], hab["licencia_vencimiento"],
            hab["tarjeta_estado"], hab["tarjeta_saldo"], hab["litros_autorizados"],
        )

    return render_template(
        "habilitaciones/detalle.html",
        hab=hab,
        despacho=despacho,
        avisos=avisos,
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
        SELECT s.id, s.nombre, s.tipo, s.gasolinera_id, s.litros_reservados, s.activo,
               cl.nombre AS cliente_nombre
        FROM subinventarios s
        LEFT JOIN clientes cl ON cl.id = s.cliente_id
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
        modo = request.form.get("modo", "despacho").strip()
        if modo not in ("despacho", "reserva"):
            modo = "despacho"
        sub_modo = request.form.get("sub_modo", "existente").strip()
        subinventario_id = request.form.get("subinventario_id", "").strip() or None
        sub_nombre_nuevo = request.form.get("sub_nombre_nuevo", "").strip()
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
        elif modo == "reserva" and sub_modo == "existente" and not subinventario_id:
            error = "Debe seleccionar un subinventario existente, o elegir crear uno nuevo."
        elif modo == "reserva" and sub_modo == "nuevo" and not sub_nombre_nuevo:
            error = "Debe indicar el nombre del subinventario nuevo."
        else:
            try:
                litros = float(litros_str.replace(",", "."))
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."
            if not error and litros <= 0:
                error = "Los litros autorizados deben ser mayores a cero."
            if not error and modo == "despacho" and not subinventario_id:
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
                conn2 = conectar()
                cur2 = conn2.cursor()
                error, tarjeta_check, unidad_check = _validar_estructural(
                    cur2, cliente_id, unidad_id, gasolinera_id, tarjeta_id,
                    subinventario_id, litros, verificar_sub_litros=(modo == "despacho"),
                )
                conn2.close()

        if not error:
            conn = conectar()
            cur = conn.cursor()
            try:
                if modo == "reserva":
                    if sub_modo == "nuevo":
                        resolved_sub_id = crear_subinventario(
                            cur, gasolinera_id, sub_nombre_nuevo, "cliente", cliente_id, 0
                        )
                    else:
                        resolved_sub_id = int(subinventario_id)

                    cur.execute("""
                        INSERT INTO habilitaciones
                            (cliente_id, unidad_id, gasolinera_id, tarjeta_id, subinventario_id,
                             litros_autorizados, fecha_habilitacion, fecha_vencimiento,
                             estado, observaciones, creado_por)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'en_reserva', ?, ?)
                    """, (cliente_id, unidad_id, gasolinera_id, tarjeta_id, resolved_sub_id,
                          litros, fecha_hab, fecha_venc, observaciones or None, session.get("user_id")))
                    nuevo_id = cur.lastrowid

                    ajustar_reserva(cur, gasolinera_id, resolved_sub_id, litros)

                    cur.execute("""
                        INSERT INTO movimientos
                            (tipo, fecha, gasolinera_id, cliente_id, vehiculo_id,
                             subinventario_destino_id, litros, responsable_id, observaciones)
                        VALUES ('habilitacion', ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (fecha_hab, gasolinera_id, cliente_id, unidad_id, resolved_sub_id,
                          litros, session.get("user_id"),
                          f"Habilitación #{nuevo_id} — apartada en reserva de subinventario"))
                else:
                    cur.execute("""
                        INSERT INTO habilitaciones
                            (cliente_id, unidad_id, gasolinera_id, tarjeta_id, subinventario_id,
                             litros_autorizados, fecha_habilitacion, fecha_vencimiento,
                             estado, observaciones, creado_por)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
                    """, (cliente_id, unidad_id, gasolinera_id, tarjeta_id, subinventario_id,
                          litros, fecha_hab, fecha_venc, observaciones or None, session.get("user_id")))
                    nuevo_id = cur.lastrowid
            except SubinventarioError as e:
                error = str(e)
                conn.close()
            else:
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


# ── Editar (solo pendiente) ──────────────────────────────────────────────────

@habilitaciones_bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/habilitaciones/{id}?access_error=Solo+Admin+y+PM+pueden+editar")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM habilitaciones WHERE id = ?", (id,))
    hab = cur.fetchone()

    if not hab:
        conn.close()
        return redirect("/habilitaciones")

    if hab["estado"] != "pendiente":
        conn.close()
        return redirect(f"/habilitaciones/{id}?access_error=Solo+se+pueden+editar+habilitaciones+pendientes")

    cur.execute("SELECT id, nombre, codigo FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    cur.execute("""
        SELECT v.id, v.chapa, v.cliente_id, v.tipo_combustible, v.estado,
               ch.nombre AS chofer_nombre, ch.licencia_vencimiento
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        WHERE v.estado = 'activo' OR v.id = ?
        ORDER BY v.chapa ASC
    """, (hab["unidad_id"],))
    unidades = cur.fetchall()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    cur.execute("""
        SELECT t.id, t.numero_parcial, t.gasolinera_id, t.tipo_combustible,
               t.saldo_usable_l, t.estado
        FROM tarjetas t
        WHERE t.estado = 'activa' OR t.id = ?
        ORDER BY t.numero_parcial ASC
    """, (hab["tarjeta_id"],))
    tarjetas = cur.fetchall()
    cur.execute("""
        SELECT s.id, s.nombre, s.tipo, s.gasolinera_id, s.litros_reservados, s.activo,
               cl.nombre AS cliente_nombre
        FROM subinventarios s
        LEFT JOIN clientes cl ON cl.id = s.cliente_id
        WHERE s.activo = 1 OR s.id = ?
        ORDER BY s.nombre ASC
    """, (hab["subinventario_id"],))
    subinventarios = cur.fetchall()

    # Avisos de estado con los datos actuales, visibles en el formulario de edición
    # (independiente de si ya hubo un POST): sirven para saber qué regularizar antes
    # de aprobar, aun si todavía no se tocó nada del formulario.
    cur.execute("""
        SELECT v.estado AS unidad_estado, v.chofer_id, ch.licencia_vencimiento,
               t.estado AS tarjeta_estado, t.saldo_usable_l
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        CROSS JOIN tarjetas t
        WHERE v.id = ? AND t.id = ?
    """, (hab["unidad_id"], hab["tarjeta_id"]))
    estado_actual = cur.fetchone()
    conn.close()

    avisos = _calcular_avisos_estado(
        estado_actual["unidad_estado"], estado_actual["chofer_id"], estado_actual["licencia_vencimiento"],
        estado_actual["tarjeta_estado"], estado_actual["saldo_usable_l"], hab["litros_autorizados"],
    )

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
            if not error and not subinventario_id:
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
                conn2 = conectar()
                cur2 = conn2.cursor()
                error, _, _ = _validar_estructural(
                    cur2, cliente_id, unidad_id, gasolinera_id, tarjeta_id,
                    subinventario_id, litros, verificar_sub_litros=True,
                )
                conn2.close()

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                UPDATE habilitaciones
                SET cliente_id = ?, unidad_id = ?, gasolinera_id = ?, tarjeta_id = ?,
                    subinventario_id = ?, litros_autorizados = ?, fecha_habilitacion = ?,
                    fecha_vencimiento = ?, observaciones = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND estado = 'pendiente'
            """, (cliente_id, unidad_id, gasolinera_id, tarjeta_id, subinventario_id,
                  litros, fecha_hab, fecha_venc, observaciones or None, id))
            if cur.rowcount == 0:
                conn.close()
                return redirect(f"/habilitaciones/{id}?access_error=La+habilitación+cambió+de+estado,+no+se+guardó+la+edición")
            conn.commit()
            conn.close()
            return redirect(f"/habilitaciones/{id}?ok=1")

    return render_template(
        "habilitaciones/editar.html",
        hab=hab,
        error=error,
        avisos=avisos,
        clientes=clientes,
        unidades=unidades,
        gasolineras=gasolineras,
        tarjetas=tarjetas,
        subinventarios=subinventarios,
        hoy=date.today().isoformat(),
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
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
    tarjeta_link = None
    litros = float(hab["litros_autorizados"])

    factor = obtener_factor(cur)

    if hab["unidad_estado"] != "activo":
        error = "La unidad no está activa."
    elif hab["chofer_id"] and hab["licencia_vencimiento"] and hab["licencia_vencimiento"] < date.today().isoformat():
        error = f"El chofer tiene la licencia vencida ({hab['licencia_vencimiento']})."
    elif hab["tarjeta_estado"] != "activa":
        error = "La tarjeta no está activa."
    elif float(hab["saldo_usable_l"]) < litros - 0.001:
        error = (
            f"Saldo insuficiente en la tarjeta. Disponible: {float(hab['saldo_usable_l']):,.2f} L "
            f"(≈ ${calcular_usd_desde_litros(hab['saldo_usable_l'], factor):,.2f} USD), "
            f"requerido: {litros:,.2f} L."
        )
        tarjeta_link = hab["tarjeta_id"]
    elif hab["subinventario_id"] and hab["sub_litros"] is not None:
        if float(hab["sub_litros"]) < litros - 0.001:
            error = (
                f"El subinventario tiene {float(hab['sub_litros']):,.2f} L reservados, "
                f"insuficiente para {litros:,.2f} L."
            )

    if error:
        conn.close()
        link_param = f"&tarjeta_link={tarjeta_link}" if tarjeta_link else ""
        return redirect(f"/habilitaciones/{id}?access_error={error.replace(' ', '+')}{link_param}")

    cur.execute("""
        UPDATE habilitaciones
        SET estado = 'aprobada', aprobado_por = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (session.get("user_id"), id))
    conn.commit()
    conn.close()
    return redirect(f"/habilitaciones/{id}?ok=1")


# ── Liberar (de en_reserva a aprobada) ──────────────────────────────────────────

@habilitaciones_bp.route("/<int:id>/liberar", methods=["POST"])
def liberar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/habilitaciones/{id}?access_error=Solo+Admin+y+PM+pueden+liberar")

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

    if hab["estado"] != "en_reserva":
        conn.close()
        return redirect(f"/habilitaciones/{id}?access_error=Solo+se+pueden+liberar+habilitaciones+en+reserva")

    error = None
    tarjeta_link = None
    litros = float(hab["litros_autorizados"])

    factor = obtener_factor(cur)

    if hab["unidad_estado"] != "activo":
        error = "La unidad no está activa."
    elif hab["chofer_id"] and hab["licencia_vencimiento"] and hab["licencia_vencimiento"] < date.today().isoformat():
        error = f"El chofer tiene la licencia vencida ({hab['licencia_vencimiento']})."
    elif hab["tarjeta_estado"] != "activa":
        error = "La tarjeta no está activa."
    elif float(hab["saldo_usable_l"]) < litros - 0.001:
        error = (
            f"Saldo insuficiente en la tarjeta. Disponible: {float(hab['saldo_usable_l']):,.2f} L "
            f"(≈ ${calcular_usd_desde_litros(hab['saldo_usable_l'], factor):,.2f} USD), "
            f"requerido: {litros:,.2f} L."
        )
        tarjeta_link = hab["tarjeta_id"]
    elif hab["subinventario_id"] and hab["sub_litros"] is not None:
        if float(hab["sub_litros"]) < litros - 0.001:
            error = (
                f"El subinventario tiene {float(hab['sub_litros']):,.2f} L reservados, "
                f"insuficiente para {litros:,.2f} L."
            )

    if error:
        conn.close()
        link_param = f"&tarjeta_link={tarjeta_link}" if tarjeta_link else ""
        return redirect(f"/habilitaciones/{id}?access_error={error.replace(' ', '+')}{link_param}")

    # No se toca litros_reservados ni movimientos aquí: la reserva ya se descontó
    # del disponible al apartar (crear en modo reserva). El consumo real del
    # subinventario ocurre al despachar, con el código ya existente, sin cambios.
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
    cur.execute("""
        SELECT estado, gasolinera_id, subinventario_id, litros_autorizados
        FROM habilitaciones WHERE id = ?
    """, (id,))
    row = cur.fetchone()

    if not row or row["estado"] not in ("pendiente", "aprobada", "en_reserva"):
        conn.close()
        return redirect(f"/habilitaciones/{id}?access_error=No+se+puede+cancelar+en+estado+actual")

    observaciones_final = observaciones

    if row["estado"] == "en_reserva" and row["subinventario_id"]:
        litros_autorizados = float(row["litros_autorizados"])
        anterior, nuevo = ajustar_reserva(
            cur, row["gasolinera_id"], row["subinventario_id"], -litros_autorizados
        )
        litros_devueltos = anterior - nuevo
        if litros_devueltos + 0.001 < litros_autorizados:
            observaciones_final = (
                f"{observaciones} — Nota: se devolvieron {litros_devueltos:,.2f} L al disponible "
                f"(de {litros_autorizados:,.2f} L apartados); el subinventario ya tenía menos "
                f"reservado de lo esperado, posiblemente por un ajuste manual posterior."
            )

    cur.execute("""
        UPDATE habilitaciones
        SET estado = 'cancelada', observaciones = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (observaciones_final, id))
    conn.commit()
    conn.close()
    return redirect(f"/habilitaciones/{id}?ok=1")
