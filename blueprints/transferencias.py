import logging

from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS
from utils.auth import requiere_login, requiere_staff
from utils.stock import stock_deposito
from utils import mailer

logger = logging.getLogger(__name__)

transferencias_bp = Blueprint("transferencias", __name__, url_prefix="/transferencias")

_DIFF_TOLERANCIA = 0.005  # 0.5%
_ROLES_TRANSFERENCIAS = ["admin", "puesto_de_mando"]


def _requiere_admin_pm():
    return session.get("rol") not in _ROLES_TRANSFERENCIAS




@transferencias_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    filtro_deposito = request.args.get("deposito_id", "").strip()
    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()

    condiciones = []
    params = []

    if filtro_deposito:
        condiciones.append("t.deposito_origen_id = ?")
        params.append(filtro_deposito)
    if filtro_gasolinera:
        condiciones.append("t.gasolinera_destino_id = ?")
        params.append(filtro_gasolinera)
    if filtro_estado:
        condiciones.append("t.estado = ?")
        params.append(filtro_estado)
    if filtro_desde:
        condiciones.append("t.fecha_salida >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        condiciones.append("t.fecha_salida <= ?")
        params.append(filtro_hasta)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT t.id, t.fecha_salida, t.fecha_llegada, t.tipo_combustible,
               t.litros_solicitados, t.litros_recibidos, t.litros_distribuidos, t.pipa_chapa,
               t.chofer_pipa, t.no_documento, t.estado,
               t.deposito_origen_id,
               d.nombre AS deposito_nombre,
               g.nombre AS gasolinera_nombre,
               u.nombre AS responsable_nombre
        FROM transferencias t
        JOIN depositos d ON d.id = t.deposito_origen_id
        JOIN gasolineras g ON g.id = t.gasolinera_destino_id
        JOIN usuarios u ON u.id = t.responsable_id
        {where}
        ORDER BY t.fecha_salida DESC, t.id DESC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM depositos WHERE estado = 'activo' ORDER BY nombre ASC")
    depositos = cur.fetchall()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    conn.close()

    return render_template(
        "transferencias/listado.html",
        lista=lista,
        depositos=depositos,
        gasolineras=gasolineras,
        filtro_deposito=filtro_deposito,
        filtro_gasolinera=filtro_gasolinera,
        filtro_estado=filtro_estado,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@transferencias_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/transferencias?access_error=Solo+Admin+y+PM+pueden+crear+transferencias")

    error = None

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, tipo_combustible FROM depositos WHERE estado = 'activo' ORDER BY nombre ASC")
    depositos = cur.fetchall()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    cur.execute("""
        SELECT gasolinera_id, tipo_combustible
        FROM tarjetas
        WHERE estado = 'activa'
        GROUP BY gasolinera_id, tipo_combustible
    """)
    _tar_rows = cur.fetchall()
    conn.close()
    tarjetas_por_gasolinera = {}
    for row in _tar_rows:
        gid = str(row["gasolinera_id"])
        tarjetas_por_gasolinera.setdefault(gid, []).append(row["tipo_combustible"])

    if request.method == "POST":
        deposito_id = request.form.get("deposito_origen_id", "").strip()
        gasolinera_id = request.form.get("gasolinera_destino_id", "").strip()
        tipo_combustible = request.form.get("tipo_combustible", "").strip()
        litros_str = request.form.get("litros_solicitados", "0").strip()
        fecha_salida = request.form.get("fecha_salida", "").strip()
        chofer_pipa = request.form.get("chofer_pipa", "").strip()
        no_documento = request.form.get("no_documento", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        if not deposito_id:
            error = "Debe seleccionar un depósito origen."
        elif not gasolinera_id:
            error = "Debe seleccionar una gasolinera destino."
        elif tipo_combustible not in TIPOS_COMBUSTIBLE:
            error = "Tipo de combustible no válido."
        elif not fecha_salida:
            error = "La fecha de salida es obligatoria."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."

            if not error and litros <= 0:
                error = "Los litros solicitados deben ser mayores a cero."

        advertencia_tarjeta = None
        sin_tarjeta_ok = request.form.get("sin_tarjeta_ok", "").strip() == "1"

        if not error:
            # Verificar stock suficiente — del combustible específico, no el total del depósito.
            conn = conectar()
            cur = conn.cursor()
            stock = stock_deposito(cur, int(deposito_id), tipo_combustible)
            if litros > stock + 0.001:
                tc_label_err = TIPOS_COMBUSTIBLE_LABELS.get(tipo_combustible, tipo_combustible)
                error = (
                    f"Stock insuficiente de {tc_label_err}. El depósito tiene {stock:,.2f} L "
                    f"de {tc_label_err} y se solicitan {litros:,.2f} L."
                )
                conn.close()

            if not error and not sin_tarjeta_ok:
                cur.execute("""
                    SELECT COUNT(*) AS n FROM tarjetas
                    WHERE gasolinera_id = ? AND tipo_combustible = ? AND estado = 'activa'
                """, (gasolinera_id, tipo_combustible))
                if cur.fetchone()["n"] == 0:
                    nombre_gas = next(
                        (g["nombre"] for g in gasolineras if str(g["id"]) == gasolinera_id), gasolinera_id
                    )
                    tc_label = TIPOS_COMBUSTIBLE_LABELS.get(tipo_combustible, tipo_combustible)
                    advertencia_tarjeta = (
                        f"{nombre_gas} no tiene tarjetas Fincimex activas de {tc_label}. "
                        f"El combustible llegará, pero no se podrá despachar hasta que se asigne saldo a una tarjeta."
                    )
                    conn.close()

            if not error and not advertencia_tarjeta:
                cur.execute("""
                    INSERT INTO transferencias
                        (deposito_origen_id, gasolinera_destino_id, tipo_combustible,
                         litros_solicitados, fecha_salida, chofer_pipa,
                         no_documento, observaciones, responsable_id, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'en_transito')
                """, (deposito_id, gasolinera_id, tipo_combustible, litros,
                      fecha_salida, chofer_pipa or None,
                      no_documento or None, observaciones or None, session.get("user_id")))
                nueva_id = cur.lastrowid
                # Insertar movimiento de salida — descuenta del depósito, con su tipo real
                cur.execute("""
                    INSERT INTO movimientos
                        (tipo, fecha, deposito_id, litros, tipo_combustible, responsable_id, observaciones)
                    VALUES ('transferencia_salida', ?, ?, ?, ?, ?, ?)
                """, (
                    fecha_salida, deposito_id, litros, tipo_combustible, session.get("user_id"),
                    f"Transferencia #{nueva_id} → {gasolinera_id}",
                ))
                conn.commit()
                conn.close()
                return redirect("/transferencias?ok=1")
    else:
        advertencia_tarjeta = None

    import json
    from datetime import date
    return render_template(
        "transferencias/crear.html",
        error=error,
        advertencia_tarjeta=advertencia_tarjeta if request.method == "POST" else None,
        depositos=depositos,
        gasolineras=gasolineras,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
        deposito_pre=request.args.get("deposito_id", "") or request.form.get("deposito_origen_id", ""),
        tarjetas_por_gasolinera_json=json.dumps(tarjetas_por_gasolinera),
        gasolineras_nombres_json=json.dumps({str(g["id"]): g["nombre"] for g in gasolineras}),
        form_vals=request.form if request.method == "POST" else {},
    )


@transferencias_bp.route("/<int:id>/gestionar")
def gestionar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/transferencias?access_error=Solo+Admin+y+PM")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.*, d.nombre AS deposito_nombre, g.nombre AS gasolinera_nombre
        FROM transferencias t
        JOIN depositos d ON d.id = t.deposito_origen_id
        JOIN gasolineras g ON g.id = t.gasolinera_destino_id
        WHERE t.id = ?
    """, (id,))
    transferencia = cur.fetchone()

    if not transferencia:
        conn.close()
        return redirect("/transferencias")

    conn.close()

    from datetime import date as _date
    return render_template(
        "transferencias/gestionar.html",
        transferencia=transferencia,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=_date.today().isoformat(),
    )


@transferencias_bp.route("/<int:id>/confirmar_llegada", methods=["GET", "POST"])
def confirmar_llegada(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/transferencias?access_error=Solo+Admin+y+PM+pueden+confirmar+llegadas")

    if request.method == "GET":
        return redirect(f"/transferencias/{id}/gestionar")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.*, d.nombre AS deposito_nombre, g.nombre AS gasolinera_nombre
        FROM transferencias t
        JOIN depositos d ON d.id = t.deposito_origen_id
        JOIN gasolineras g ON g.id = t.gasolinera_destino_id
        WHERE t.id = ?
    """, (id,))
    transferencia = cur.fetchone()
    conn.close()

    if not transferencia or transferencia["estado"] != "en_transito":
        return redirect("/transferencias?access_error=Transferencia+no+disponible")

    error = None
    advertencia = None

    if request.method == "POST":
        litros_str = request.form.get("litros_recibidos", "").strip()
        fecha_llegada = request.form.get("fecha_llegada", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        if not litros_str:
            error = "Los litros recibidos son obligatorios."
        elif not fecha_llegada:
            error = "La fecha de llegada es obligatoria."
        else:
            try:
                litros_recibidos = float(litros_str)
            except ValueError:
                error = "Los litros deben ser un número válido."
                litros_recibidos = 0.0

            if not error and litros_recibidos < 0:
                error = "Los litros recibidos no pueden ser negativos."

        if not error:
            litros_sol = float(transferencia["litros_solicitados"])
            diferencia_pct = abs(litros_recibidos - litros_sol) / litros_sol if litros_sol else 0
            if diferencia_pct > _DIFF_TOLERANCIA and not observaciones:
                error = (
                    f"La diferencia entre litros solicitados ({litros_sol:,.2f} L) y recibidos "
                    f"({litros_recibidos:,.2f} L) supera el 0.5%. "
                    f"Debe añadir una observación obligatoria."
                )

        sin_tarjeta_ok = request.form.get("sin_tarjeta_ok", "").strip() == "1"

        if not error:
            conn = conectar()
            cur = conn.cursor()

            # Antes: BLOQUEO DURO. Ahora: aviso descartable (el PM puede continuar)
            if not sin_tarjeta_ok:
                cur.execute("""
                    SELECT COUNT(*) AS n FROM tarjetas
                    WHERE gasolinera_id = ? AND tipo_combustible = ? AND estado = 'activa'
                """, (transferencia["gasolinera_destino_id"], transferencia["tipo_combustible"]))
                if cur.fetchone()["n"] == 0:
                    tc_label = TIPOS_COMBUSTIBLE_LABELS.get(transferencia["tipo_combustible"], transferencia["tipo_combustible"])
                    advertencia = (
                        f"⚠️ {transferencia['gasolinera_nombre']} no tiene tarjetas Fincimex activas de {tc_label}. "
                        f"El combustible llegará al stock, pero no se podrá despachar hasta que se asigne saldo a una tarjeta."
                    )
                    conn.close()
                    try:
                        mailer.staff_sin_cobertura_saldo(
                            transferencia["gasolinera_nombre"], tc_label,
                            "No hay tarjetas Fincimex activas para recibir el saldo de esta transferencia.",
                        )
                    except Exception:
                        logger.error("Error notificando staff de sin cobertura (transferencia #%s)",
                                     id, exc_info=True)
                    from datetime import date as _d2
                    return render_template(
                        "transferencias/confirmar_llegada.html",
                        transferencia=transferencia,
                        error=None,
                        advertencia=advertencia,
                        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
                        hoy=_d2.today().isoformat(),
                        form_vals=request.form,
                    )

            cur.execute("""
                UPDATE transferencias
                SET estado = 'recibida', litros_recibidos = ?,
                    fecha_llegada = ?, observaciones = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (litros_recibidos, fecha_llegada, observaciones or None, id))
            # Insertar movimiento de entrada — suma a la gasolinera
            cur.execute("""
                INSERT INTO movimientos
                    (tipo, fecha, gasolinera_id, tipo_combustible, litros, responsable_id, observaciones)
                VALUES ('transferencia_entrada', ?, ?, ?, ?, ?, ?)
            """, (
                fecha_llegada,
                transferencia["gasolinera_destino_id"],
                transferencia["tipo_combustible"],
                litros_recibidos,
                session.get("user_id"),
                f"Llegada transferencia #{id} desde depósito {transferencia['deposito_nombre']}",
            ))
            conn.commit()
            conn.close()

            try:
                mailer.staff_combustible_sin_distribuir(
                    transferencia["gasolinera_nombre"], transferencia["tipo_combustible"],
                    litros_recibidos, id,
                )
            except Exception:
                logger.error("Error notificando staff de combustible sin distribuir (transferencia #%s)",
                             id, exc_info=True)

            return redirect(f"/transferencias/{id}/gestionar?ok=1")

    from datetime import date
    return render_template(
        "transferencias/confirmar_llegada.html",
        transferencia=transferencia,
        error=error,
        advertencia=advertencia,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
    )


@transferencias_bp.route("/<int:id>/anular", methods=["POST"])
def anular(id):
    redir = requiere_login()
    if redir:
        return redir
    if session.get("rol") != "admin":
        return redirect("/transferencias?access_error=Solo+Admin+puede+anular+transferencias")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transferencias WHERE id = ?", (id,))
    transferencia = cur.fetchone()

    if not transferencia or transferencia["estado"] != "en_transito":
        conn.close()
        return redirect("/transferencias?access_error=Solo+se+pueden+anular+transferencias+en+tránsito")

    # Anular: revertir movimiento de salida → insertar anulacion
    cur.execute(
        "UPDATE transferencias SET estado = 'anulada', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (id,)
    )
    cur.execute("""
        INSERT INTO movimientos
            (tipo, fecha, deposito_id, litros, tipo_combustible, responsable_id, observaciones)
        VALUES ('transferencia_anulacion', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
    """, (
        transferencia["deposito_origen_id"],
        transferencia["litros_solicitados"],
        transferencia["tipo_combustible"],
        session.get("user_id"),
        f"Anulación transferencia #{id}",
    ))
    conn.commit()
    conn.close()
    return redirect("/transferencias?ok=1")
