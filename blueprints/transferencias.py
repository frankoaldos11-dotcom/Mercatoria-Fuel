from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM
from utils.auth import requiere_login

transferencias_bp = Blueprint("transferencias", __name__, url_prefix="/transferencias")

_DIFF_TOLERANCIA = 0.005  # 0.5%


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


def _stock_deposito(cur, deposito_id):
    cur.execute("""
        SELECT COALESCE(SUM(
            CASE WHEN tipo = 'transferencia_salida' THEN -litros ELSE litros END
        ), 0) AS stock
        FROM movimientos
        WHERE deposito_id = ?
        AND tipo IN ('recepcion', 'transferencia_salida', 'transferencia_anulacion')
    """, (deposito_id,))
    return float(cur.fetchone()["stock"] or 0)


@transferencias_bp.route("/")
def listado():
    redir = requiere_login()
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
               t.litros_solicitados, t.litros_recibidos, t.pipa_chapa,
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
    conn.close()

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

        if not error:
            # Verificar stock suficiente
            conn = conectar()
            cur = conn.cursor()
            stock = _stock_deposito(cur, int(deposito_id))
            if litros > stock + 0.001:
                error = (
                    f"Stock insuficiente. El depósito tiene {stock:,.2f} L "
                    f"y se solicitan {litros:,.2f} L."
                )
                conn.close()
            else:
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
                # Insertar movimiento de salida — descuenta del depósito
                cur.execute("""
                    INSERT INTO movimientos
                        (tipo, fecha, deposito_id, litros, responsable_id, observaciones)
                    VALUES ('transferencia_salida', ?, ?, ?, ?, ?)
                """, (
                    fecha_salida, deposito_id, litros, session.get("user_id"),
                    f"Transferencia #{nueva_id} → {gasolinera_id}",
                ))
                conn.commit()
                conn.close()
                return redirect("/transferencias?ok=1")

    from datetime import date
    return render_template(
        "transferencias/crear.html",
        error=error,
        depositos=depositos,
        gasolineras=gasolineras,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
        deposito_pre=request.args.get("deposito_id", "") or request.form.get("deposito_origen_id", ""),
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

    tarjetas = []
    if transferencia["estado"] == "recibida":
        cur.execute("""
            SELECT id, numero_parcial, tipo_combustible, saldo_usable_l
            FROM tarjetas
            WHERE gasolinera_id = ? AND estado = 'activa'
            ORDER BY numero_parcial ASC
        """, (transferencia["gasolinera_destino_id"],))
        tarjetas = cur.fetchall()

    conn.close()

    from datetime import date as _date
    return render_template(
        "transferencias/gestionar.html",
        transferencia=transferencia,
        tarjetas=tarjetas,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=_date.today().isoformat(),
    )


@transferencias_bp.route("/<int:id>/distribuir", methods=["POST"])
def distribuir(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/transferencias/{id}/gestionar?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transferencias WHERE id = ? AND estado = 'recibida'", (id,))
    transferencia = cur.fetchone()

    if not transferencia:
        conn.close()
        return redirect("/transferencias")

    assignments = []
    for key, value in request.form.items():
        if key.startswith("litros_tarjeta_") and value.strip():
            try:
                tarjeta_id = int(key.replace("litros_tarjeta_", ""))
                litros_val = float(value.strip().replace(",", "."))
                if litros_val > 0:
                    assignments.append((tarjeta_id, litros_val))
            except (ValueError, KeyError):
                pass

    if not assignments:
        conn.close()
        return redirect(f"/transferencias/{id}/gestionar?access_error=Ingresa+litros+para+al+menos+una+tarjeta")

    suma_asignada = sum(litros_val for _, litros_val in assignments)
    litros_requeridos = float(transferencia["litros_recibidos"])
    if abs(suma_asignada - litros_requeridos) > 0.005:
        conn.close()
        return redirect(
            f"/transferencias/{id}/gestionar?access_error="
            f"La+suma+({suma_asignada:.2f}+L)+debe+igualar+exactamente+{litros_requeridos:.2f}+L+recibidos"
        )

    from datetime import date as _date
    fecha_hoy = _date.today().isoformat()
    for tarjeta_id, litros_val in assignments:
        cur.execute("""
            INSERT INTO movimientos
                (tipo, fecha, gasolinera_id, tipo_combustible, litros, responsable_id, observaciones)
            VALUES ('asignacion_tarjeta', ?, ?, ?, ?, ?, ?)
        """, (
            fecha_hoy,
            transferencia["gasolinera_destino_id"],
            transferencia["tipo_combustible"],
            litros_val,
            session.get("user_id"),
            f"Asignación a tarjeta #{tarjeta_id} desde transferencia #{id}",
        ))
        cur.execute(
            "UPDATE tarjetas SET saldo_usable_l = saldo_usable_l + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (litros_val, tarjeta_id)
        )

    conn.commit()
    conn.close()
    return redirect(f"/transferencias/{id}/gestionar?ok=1")


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

        if not error:
            conn = conectar()
            cur = conn.cursor()
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
            (tipo, fecha, deposito_id, litros, responsable_id, observaciones)
        VALUES ('transferencia_anulacion', CURRENT_TIMESTAMP, ?, ?, ?, ?)
    """, (
        transferencia["deposito_origen_id"],
        transferencia["litros_solicitados"],
        session.get("user_id"),
        f"Anulación transferencia #{id}",
    ))
    conn.commit()
    conn.close()
    return redirect("/transferencias?ok=1")
