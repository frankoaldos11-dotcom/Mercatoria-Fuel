from datetime import date

from flask import Blueprint, render_template, request, redirect, session
from werkzeug.security import generate_password_hash

from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM, ESTADOS_TARJETA
from utils.auth import requiere_login

tarjetas_bp = Blueprint("tarjetas", __name__, url_prefix="/tarjetas")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


def _stock_gasolinera(cur, gasolinera_id):
    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS stock
        FROM movimientos
        WHERE gasolinera_id = ? AND tipo = 'transferencia_entrada'
    """, (gasolinera_id,))
    return float(cur.fetchone()["stock"] or 0)


# ── Listado ───────────────────────────────────────────────────────────────────

@tarjetas_bp.route("/")
def listado():
    redir = requiere_login()
    if redir:
        return redir

    buscar = request.args.get("buscar", "").strip()
    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_combustible = request.args.get("combustible", "").strip()

    condiciones = []
    params = []

    if buscar:
        condiciones.append("(t.numero_parcial LIKE ? OR g.nombre LIKE ?)")
        like = f"%{buscar}%"
        params.extend([like, like])
    if filtro_gasolinera:
        condiciones.append("t.gasolinera_id = ?")
        params.append(filtro_gasolinera)
    if filtro_estado:
        condiciones.append("t.estado = ?")
        params.append(filtro_estado)
    if filtro_combustible:
        condiciones.append("t.tipo_combustible = ?")
        params.append(filtro_combustible)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT t.id, t.numero_parcial, t.tipo_combustible,
               t.saldo_usable_l, t.saldo_retenido_l, t.estado,
               g.nombre AS gasolinera_nombre,
               (SELECT COUNT(*) FROM devoluciones_tarjetas d
                WHERE d.tarjeta_id = t.id AND d.estado = 'pendiente') AS devoluciones_pendientes
        FROM tarjetas t
        JOIN gasolineras g ON g.id = t.gasolinera_id
        {where}
        ORDER BY t.id ASC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    conn.close()

    return render_template(
        "tarjetas/listado.html",
        lista=lista,
        gasolineras=gasolineras,
        buscar=buscar,
        filtro_gasolinera=filtro_gasolinera,
        filtro_estado=filtro_estado,
        filtro_combustible=filtro_combustible,
        estados_tarjeta=ESTADOS_TARJETA,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


# ── Detalle ───────────────────────────────────────────────────────────────────

@tarjetas_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.*, g.nombre AS gasolinera_nombre
        FROM tarjetas t
        JOIN gasolineras g ON g.id = t.gasolinera_id
        WHERE t.id = ?
    """, (id,))
    tarjeta = cur.fetchone()

    if not tarjeta:
        conn.close()
        return redirect("/tarjetas")

    # Historial de recargas
    cur.execute("""
        SELECT r.id, r.fecha, r.litros_recargados, r.estado, r.observaciones,
               u.nombre AS responsable_nombre
        FROM recargas_tarjetas r
        JOIN usuarios u ON u.id = r.responsable_id
        WHERE r.tarjeta_id = ?
        ORDER BY r.fecha DESC, r.id DESC
        LIMIT 50
    """, (id,))
    recargas = cur.fetchall()

    # Historial de devoluciones
    cur.execute("""
        SELECT d.id, d.fecha_incidente, d.litros_retenidos, d.slip_inicial,
               d.slip_devolucion, d.slip_restante, d.fecha_estimada_liberacion,
               d.fecha_liberacion_real, d.estado, d.observaciones,
               u.nombre AS responsable_nombre
        FROM devoluciones_tarjetas d
        JOIN usuarios u ON u.id = d.responsable_id
        WHERE d.tarjeta_id = ?
        ORDER BY d.fecha_incidente DESC, d.id DESC
    """, (id,))
    devoluciones = cur.fetchall()
    conn.close()

    return render_template(
        "tarjetas/detalle.html",
        tarjeta=tarjeta,
        recargas=recargas,
        devoluciones=devoluciones,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
    )


# ── Crear ─────────────────────────────────────────────────────────────────────

@tarjetas_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/tarjetas?access_error=Solo+Admin+y+PM+pueden+crear+tarjetas")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        numero_completo = request.form.get("numero_completo", "").strip().replace(" ", "").replace("-", "")
        pin = request.form.get("pin", "").strip()
        gasolinera_id = request.form.get("gasolinera_id", "").strip()
        tipo_combustible = request.form.get("tipo_combustible", "").strip()
        saldo_str = request.form.get("saldo_usable_l", "0").strip()
        estado = request.form.get("estado", "activa").strip()
        notas = request.form.get("notas", "").strip()

        if not numero_completo or not numero_completo.isdigit() or len(numero_completo) != 16:
            error = "El número de tarjeta debe tener exactamente 16 dígitos."
        elif not pin:
            error = "El PIN es obligatorio."
        elif not gasolinera_id:
            error = "Debe seleccionar una gasolinera."
        elif tipo_combustible not in TIPOS_COMBUSTIBLE:
            error = "Tipo de combustible no válido."
        elif estado not in ESTADOS_TARJETA:
            error = "Estado no válido."
        else:
            try:
                saldo_usable = float(saldo_str)
            except ValueError:
                saldo_usable = 0.0

            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM tarjetas WHERE numero_completo = ?", (numero_completo,))
            if cur.fetchone():
                error = "Ya existe una tarjeta con ese número."
                conn.close()
            else:
                numero_parcial = numero_completo[-4:]
                pin_hash = generate_password_hash(pin)
                cur.execute("""
                    INSERT INTO tarjetas
                        (numero_completo, numero_parcial, pin_hash, gasolinera_id,
                         tipo_combustible, saldo_usable_l, estado, notas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (numero_completo, numero_parcial, pin_hash, gasolinera_id,
                      tipo_combustible, saldo_usable, estado, notas or None))
                conn.commit()
                conn.close()
                return redirect("/tarjetas?ok=1")

    return render_template(
        "tarjetas/crear.html",
        error=error,
        gasolineras=gasolineras,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        estados_tarjeta=ESTADOS_TARJETA,
    )


# ── Toggle estado ─────────────────────────────────────────────────────────────

@tarjetas_bp.route("/<int:id>/toggle", methods=["POST"])
def toggle_estado(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/tarjetas?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM tarjetas WHERE id = ?", (id,))
    row = cur.fetchone()
    if row:
        nuevo = "inactiva" if row["estado"] == "activa" else "activa"
        cur.execute(
            "UPDATE tarjetas SET estado = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (nuevo, id)
        )
        conn.commit()
    conn.close()
    return redirect(f"/tarjetas/{id}?ok=1")


# ── Recargar ──────────────────────────────────────────────────────────────────

@tarjetas_bp.route("/<int:id>/recargar", methods=["GET", "POST"])
def recargar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/tarjetas/{id}?access_error=Solo+Admin+y+PM+pueden+recargar+tarjetas")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.*, g.nombre AS gasolinera_nombre
        FROM tarjetas t JOIN gasolineras g ON g.id = t.gasolinera_id
        WHERE t.id = ?
    """, (id,))
    tarjeta = cur.fetchone()
    conn.close()

    if not tarjeta:
        return redirect("/tarjetas")

    error = None

    if request.method == "POST":
        litros_str = request.form.get("litros_recargados", "0").strip()
        fecha = request.form.get("fecha", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        if not fecha:
            error = "La fecha es obligatoria."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."

            if not error and litros <= 0:
                error = "Los litros a recargar deben ser mayores a cero."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                UPDATE tarjetas
                SET saldo_usable_l = saldo_usable_l + ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (litros, id))
            cur.execute("""
                INSERT INTO recargas_tarjetas
                    (tarjeta_id, fecha, litros_recargados, responsable_id, observaciones, estado)
                VALUES (?, ?, ?, ?, ?, 'confirmada')
            """, (id, fecha, litros, session.get("user_id"), observaciones or None))
            cur.execute("""
                INSERT INTO movimientos
                    (tipo, fecha, tarjeta_id, gasolinera_id, litros, responsable_id, observaciones)
                VALUES ('recarga_tarjeta', ?, ?, ?, ?, ?, ?)
            """, (fecha, id, tarjeta["gasolinera_id"], litros, session.get("user_id"),
                  f"Recarga tarjeta ****{tarjeta['numero_parcial']}"))
            conn.commit()
            conn.close()
            return redirect(f"/tarjetas/{id}?ok=1")

    return render_template(
        "tarjetas/recargar.html",
        tarjeta=tarjeta,
        error=error,
        hoy=date.today().isoformat(),
    )


# ── Registrar devolución retenida ─────────────────────────────────────────────

@tarjetas_bp.route("/<int:id>/devolucion", methods=["GET", "POST"])
def devolucion(id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.*, g.nombre AS gasolinera_nombre
        FROM tarjetas t JOIN gasolineras g ON g.id = t.gasolinera_id
        WHERE t.id = ?
    """, (id,))
    tarjeta = cur.fetchone()
    conn.close()

    if not tarjeta:
        return redirect("/tarjetas")

    error = None

    if request.method == "POST":
        litros_str = request.form.get("litros_retenidos", "0").strip()
        fecha_incidente = request.form.get("fecha_incidente", "").strip()
        slip_inicial = request.form.get("slip_inicial", "").strip()
        slip_devolucion = request.form.get("slip_devolucion", "").strip()
        slip_restante = request.form.get("slip_restante", "").strip()
        fecha_estimada = request.form.get("fecha_estimada_liberacion", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        if not fecha_incidente:
            error = "La fecha del incidente es obligatoria."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."

            if not error and litros <= 0:
                error = "Los litros retenidos deben ser mayores a cero."
            elif not error and litros > float(tarjeta["saldo_usable_l"]) + 0.001:
                error = (
                    f"Los litros retenidos ({litros:,.2f} L) superan el saldo usable "
                    f"disponible ({float(tarjeta['saldo_usable_l']):,.2f} L)."
                )

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                UPDATE tarjetas
                SET saldo_usable_l   = saldo_usable_l   - ?,
                    saldo_retenido_l = saldo_retenido_l + ?,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (litros, litros, id))
            cur.execute("""
                INSERT INTO devoluciones_tarjetas
                    (tarjeta_id, fecha_incidente, litros_retenidos, slip_inicial,
                     slip_devolucion, slip_restante, fecha_estimada_liberacion,
                     estado, observaciones, responsable_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
            """, (id, fecha_incidente, litros,
                  slip_inicial or None, slip_devolucion or None, slip_restante or None,
                  fecha_estimada or None, observaciones or None, session.get("user_id")))
            conn.commit()
            conn.close()
            return redirect(f"/tarjetas/{id}?ok=1")

    return render_template(
        "tarjetas/devolucion.html",
        tarjeta=tarjeta,
        error=error,
        hoy=date.today().isoformat(),
    )


# ── Liberar devolución retenida ───────────────────────────────────────────────

@tarjetas_bp.route("/<int:tarjeta_id>/liberar/<int:dev_id>", methods=["POST"])
def liberar_devolucion(tarjeta_id, dev_id):
    redir = requiere_login()
    if redir:
        return redir

    fecha_real = request.form.get("fecha_liberacion_real", "").strip() or date.today().isoformat()

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM devoluciones_tarjetas
        WHERE id = ? AND tarjeta_id = ? AND estado = 'pendiente'
    """, (dev_id, tarjeta_id))
    dev = cur.fetchone()

    if not dev:
        conn.close()
        return redirect(f"/tarjetas/{tarjeta_id}?access_error=Devolución+no+disponible")

    litros = float(dev["litros_retenidos"])
    cur.execute("""
        UPDATE tarjetas
        SET saldo_usable_l   = saldo_usable_l   + ?,
            saldo_retenido_l = saldo_retenido_l - ?,
            updated_at       = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (litros, litros, tarjeta_id))
    cur.execute("""
        UPDATE devoluciones_tarjetas
        SET estado = 'liberada', fecha_liberacion_real = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (fecha_real, dev_id))
    conn.commit()
    conn.close()
    return redirect(f"/tarjetas/{tarjeta_id}?ok=1")
