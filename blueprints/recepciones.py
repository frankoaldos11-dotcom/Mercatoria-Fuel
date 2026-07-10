rom flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM
from utils.auth import requiere_login, requiere_staff
from utils.stock import stock_deposito

recepciones_bp = Blueprint("recepciones", __name__, url_prefix="/recepciones")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM




@recepciones_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    buscar = request.args.get("buscar", "").strip()
    filtro_deposito = request.args.get("deposito_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()

    condiciones = []
    params = []

    if buscar:
        condiciones.append("(r.proveedor LIKE ? OR r.no_vale LIKE ?)")
        like = f"%{buscar}%"
        params.extend([like, like])
    if filtro_deposito:
        condiciones.append("r.deposito_id = ?")
        params.append(filtro_deposito)
    if filtro_estado:
        condiciones.append("r.estado = ?")
        params.append(filtro_estado)
    if filtro_desde:
        condiciones.append("r.fecha >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        condiciones.append("r.fecha <= ?")
        params.append(filtro_hasta)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT r.id, r.fecha, r.proveedor, r.tipo_combustible,
               r.litros_factura, r.litros_recibidos, r.diferencia_l,
               r.no_vale, r.calidad_ok, r.estado, r.deposito_id,
               d.nombre AS deposito_nombre,
               u.nombre AS responsable_nombre
        FROM recepciones r
        JOIN depositos d ON d.id = r.deposito_id
        JOIN usuarios u ON u.id = r.responsable_id
        {where}
        ORDER BY r.fecha DESC, r.id DESC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM depositos WHERE estado = 'activo' ORDER BY nombre ASC")
    depositos = cur.fetchall()
    conn.close()

    return render_template(
        "recepciones/listado.html",
        lista=lista,
        depositos=depositos,
        buscar=buscar,
        filtro_deposito=filtro_deposito,
        filtro_estado=filtro_estado,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@recepciones_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/recepciones?access_error=Solo+Admin+y+PM+pueden+crear+recepciones")

    error = None

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, tipo_combustible FROM depositos WHERE estado = 'activo' ORDER BY nombre ASC")
    depositos = cur.fetchall()
    conn.close()

    if request.method == "POST":
        deposito_id = request.form.get("deposito_id", "").strip()
        fecha = request.form.get("fecha", "").strip()
        proveedor = request.form.get("proveedor", "").strip()
        tipo_combustible = request.form.get("tipo_combustible", "").strip()
        litros_factura_str = request.form.get("litros_factura", "0").strip()
        litros_recibidos_str = request.form.get("litros_recibidos", "0").strip()
        no_vale = request.form.get("no_vale", "").strip()
        calidad_ok = 1 if request.form.get("calidad_ok") else 0
        observaciones = request.form.get("observaciones", "").strip()

        if not deposito_id:
            error = "Debe seleccionar un depósito."
        elif not fecha:
            error = "La fecha es obligatoria."
        elif not proveedor:
            error = "El proveedor es obligatorio."
        elif tipo_combustible not in TIPOS_COMBUSTIBLE:
            error = "Tipo de combustible no válido."
        else:
            try:
                litros_factura = float(litros_factura_str)
                litros_recibidos = float(litros_recibidos_str)
            except ValueError:
                error = "Los litros deben ser números válidos."
                litros_factura = litros_recibidos = 0.0

            if not error and litros_factura < 0:
                error = "Los litros facturados no pueden ser negativos."
            elif not error and litros_recibidos < 0:
                error = "Los litros recibidos no pueden ser negativos."

        if not error:
            diferencia_l = litros_recibidos - litros_factura
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO recepciones
                    (deposito_id, fecha, proveedor, tipo_combustible, litros_factura,
                     litros_recibidos, diferencia_l, no_vale, calidad_ok, observaciones,
                     responsable_id, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente')
            """, (deposito_id, fecha, proveedor, tipo_combustible, litros_factura,
                  litros_recibidos, diferencia_l, no_vale or None, calidad_ok,
                  observaciones or None, session.get("user_id")))
            conn.commit()
            conn.close()
            return redirect("/recepciones?ok=1")

    from datetime import date
    return render_template(
        "recepciones/crear.html",
        error=error,
        depositos=depositos,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
        deposito_preseleccionado=request.args.get("deposito_id", ""),
    )


@recepciones_bp.route("/<int:id>/confirmar", methods=["POST"])
def confirmar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/recepciones?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recepciones WHERE id = ?", (id,))
    recepcion = cur.fetchone()

    if not recepcion or recepcion["estado"] != "pendiente":
        conn.close()
        return redirect("/recepciones?access_error=Recepción+no+disponible+para+confirmar")

    # Leer factor de conversión
    cur.execute("SELECT valor FROM configuracion WHERE clave = 'factor_litro_usd'")
    _frow = cur.fetchone()
    factor = float(_frow["valor"]) if _frow else 0.90
    litros_rec = float(recepcion["litros_recibidos"])
    monto_usd = round(litros_rec * factor, 2)

    # Confirmar: cambiar estado e insertar en movimientos de litros
    cur.execute(
        "UPDATE recepciones SET estado = 'confirmada', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (id,)
    )
    cur.execute("""
        INSERT INTO movimientos
            (tipo, fecha, deposito_id, litros, responsable_id, observaciones)
        VALUES ('recepcion', ?, ?, ?, ?, ?)
    """, (
        recepcion["fecha"],
        recepcion["deposito_id"],
        litros_rec,
        session.get("user_id"),
        f"Recepción #{id} — {recepcion['proveedor']} — Vale: {recepcion['no_vale'] or 'N/A'}",
    ))
    # Generar saldo en bolsón general Fincimex
    cur.execute("""
        INSERT INTO movimientos_saldo_fincimex
            (tipo, monto_usd, litros, factor, recepcion_id, responsable_id, observaciones)
        VALUES ('generacion', ?, ?, ?, ?, ?, ?)
    """, (
        monto_usd, litros_rec, factor, id, session.get("user_id"),
        f"Generación automática — Recepción #{id} — {recepcion['proveedor']} ({litros_rec:,.2f} L × {factor})",
    ))
    conn.commit()
    conn.close()
    return redirect("/recepciones?ok=1")


@recepciones_bp.route("/<int:id>/anular", methods=["POST"])
def anular(id):
    redir = requiere_login()
    if redir:
        return redir
    if session.get("rol") != "admin":
        return redirect("/recepciones?access_error=Solo+Admin+puede+anular+recepciones")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM recepciones WHERE id = ?", (id,))
    recepcion = cur.fetchone()

    if not recepcion or recepcion["estado"] == "anulada":
        conn.close()
        return redirect("/recepciones?access_error=Recepción+ya+anulada+o+no+existe")

    # Si estaba confirmada, verificar que el stock del depósito no quede negativo
    if recepcion["estado"] == "confirmada":
        stock_actual = stock_deposito(cur, recepcion["deposito_id"])
        stock_tras_anulacion = stock_actual - recepcion["litros_recibidos"]
        if stock_tras_anulacion < -0.001:  # tolerancia de 0.001 L por decimales flotantes
            conn.close()
            return redirect(
                f"/recepciones?access_error=No+se+puede+anular:+el+depósito+tiene+"
                f"transferencias+que+dependen+de+este+stock"
            )
        # Revertir el movimiento de recepción anulando con negativo
        cur.execute("""
            INSERT INTO movimientos
                (tipo, fecha, deposito_id, litros, responsable_id, observaciones)
            VALUES ('recepcion', CURRENT_TIMESTAMP, ?, ?, ?, ?)
        """, (
            recepcion["deposito_id"],
            -recepcion["litros_recibidos"],
            session.get("user_id"),
            f"Anulación recepción #{id}",
        ))

    cur.execute(
        "UPDATE recepciones SET estado = 'anulada', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (id,)
    )
    conn.commit()
    conn.close()
    return redirect("/recepciones?ok=1")
