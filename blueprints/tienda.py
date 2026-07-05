import uuid
import base64
import io

from flask import Blueprint, render_template, request, redirect, session, jsonify
from database import conectar

tienda_bp = Blueprint("tienda", __name__, url_prefix="/tienda")

_COMBUSTIBLE_LABELS = {
    "diesel":            "Diésel",
    "gasolina_regular":  "Gasolina Regular",
    "gasolina_especial": "Gasolina Especial",
}

_ESTADO_LABELS = {
    "pendiente":  "Pendiente",
    "aprobada":   "Aprobada",
    "completada": "Completada",
    "cancelada":  "Cancelada",
}

_ESTADO_BADGE = {
    "pendiente":  "badge-warn",
    "aprobada":   "badge-info",
    "completada": "badge-ok",
    "cancelada":  "badge-danger",
}

_ROLES_STAFF = ("admin", "pm", "supervisor")


def _requiere_cliente():
    if "usuario" not in session:
        return redirect("/login")
    if session.get("rol") != "cliente":
        return redirect("/dashboard")
    return None


# ── Portal cliente ─────────────────────────────────────────────────────────────

@tienda_bp.route("/")
def index():
    redir = _requiere_cliente()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT pc.gasolinera_id, pc.tipo_combustible, pc.precio_usd_por_litro,
               g.nombre AS gasolinera_nombre
        FROM precios_combustible pc
        JOIN gasolineras g ON g.id = pc.gasolinera_id
        WHERE pc.activo = 1 AND g.estado = 'activo'
        ORDER BY g.nombre ASC, pc.tipo_combustible ASC
    """)
    productos = cur.fetchall()
    conn.close()

    return render_template("tienda/index.html",
                           productos=productos,
                           combustible_labels=_COMBUSTIBLE_LABELS)


@tienda_bp.route("/reservar", methods=["GET", "POST"])
def reservar():
    redir = _requiere_cliente()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT pc.gasolinera_id, pc.tipo_combustible, pc.precio_usd_por_litro,
               g.nombre AS gasolinera_nombre
        FROM precios_combustible pc
        JOIN gasolineras g ON g.id = pc.gasolinera_id
        WHERE pc.activo = 1 AND g.estado = 'activo'
        ORDER BY g.nombre ASC, pc.tipo_combustible ASC
    """)
    productos = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado='activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()

    cur.execute("""
        SELECT id, placa, marca, modelo, tipo_combustible
        FROM vehiculos_tienda WHERE usuario_id=? AND activo=1 ORDER BY placa ASC
    """, (session["user_id"],))
    mis_vehiculos_activos = cur.fetchall()

    cur.execute("SELECT valor FROM configuracion WHERE clave = 'compra_minima_litros'")
    row_min = cur.fetchone()
    compra_minima = float(row_min["valor"]) if row_min else 0.0

    error = None

    if request.method == "POST":
        gid = request.form.get("gasolinera_id", "").strip()
        tc = request.form.get("tipo_combustible", "").strip()
        litros_str = request.form.get("litros", "0").strip()
        vehiculo_id_sel = request.form.get("vehiculo_id", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        try:
            litros = float(litros_str.replace(",", "."))
        except ValueError:
            litros = 0.0

        # Validación de vehículo — obligatorio
        vehiculo_id_valid = None
        desc_vehiculo = ""
        if not mis_vehiculos_activos:
            error = "Debes registrar al menos un vehículo antes de reservar."
        elif not vehiculo_id_sel:
            error = "Selecciona un vehículo registrado."
        else:
            cur.execute("""
                SELECT id, placa, marca, modelo FROM vehiculos_tienda
                WHERE id=? AND usuario_id=? AND activo=1
            """, (vehiculo_id_sel, session["user_id"]))
            vrow = cur.fetchone()
            if not vrow:
                error = "El vehículo seleccionado no es válido."
            else:
                vehiculo_id_valid = vrow["id"]
                desc_vehiculo = " / ".join(filter(None, [vrow["placa"], vrow["marca"], vrow["modelo"]]))

        if not error:
            if not gid:
                error = "Selecciona una gasolinera."
            elif not tc:
                error = "Selecciona el tipo de combustible."
            elif litros <= 0:
                error = "La cantidad de litros debe ser mayor a cero."
            elif compra_minima > 0 and litros < compra_minima:
                error = f"La cantidad mínima por reserva es {compra_minima:,.0f} L."

        if not error:
            cur.execute("""
                SELECT precio_usd_por_litro FROM precios_combustible
                WHERE gasolinera_id = ? AND tipo_combustible = ? AND activo = 1
            """, (gid, tc))
            precio_row = cur.fetchone()
            if not precio_row:
                error = "Esa combinación de gasolinera y combustible no está disponible."

        if not error:
            precio_unitario = float(precio_row["precio_usd_por_litro"])
            precio_total = round(litros * precio_unitario, 2)
            cur.execute("""
                INSERT INTO reservas_tienda
                    (usuario_id, gasolinera_id, tipo_combustible, litros_solicitados,
                     precio_usd_por_litro, precio_total_usd, descripcion_vehiculo,
                     observaciones, vehiculo_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session["user_id"], gid, tc, litros, precio_unitario, precio_total,
                  desc_vehiculo or None, observaciones or None, vehiculo_id_valid))
            nueva_id = cur.lastrowid
            conn.commit()
            conn.close()
            return redirect(f"/tienda/confirmacion/{nueva_id}")

    conn.close()

    return render_template("tienda/reservar.html",
                           productos=productos,
                           gasolineras=gasolineras,
                           mis_vehiculos=mis_vehiculos_activos,
                           combustible_labels=_COMBUSTIBLE_LABELS,
                           compra_minima=compra_minima,
                           gid_pre=request.args.get("gasolinera_id", ""),
                           tc_pre=request.args.get("tipo", ""),
                           error=error,
                           form=request.form if request.method == "POST" else {})


@tienda_bp.route("/confirmacion/<int:rid>")
def confirmacion(rid):
    redir = _requiere_cliente()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, g.nombre AS gasolinera_nombre
        FROM reservas_tienda r
        JOIN gasolineras g ON g.id = r.gasolinera_id
        WHERE r.id = ? AND r.usuario_id = ?
    """, (rid, session["user_id"]))
    reserva = cur.fetchone()
    conn.close()

    if not reserva:
        return redirect("/tienda/mis-reservas")

    return render_template("tienda/confirmacion.html",
                           reserva=reserva,
                           combustible_labels=_COMBUSTIBLE_LABELS)


@tienda_bp.route("/mis-reservas")
def mis_reservas():
    redir = _requiere_cliente()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.*, g.nombre AS gasolinera_nombre
        FROM reservas_tienda r
        JOIN gasolineras g ON g.id = r.gasolinera_id
        WHERE r.usuario_id = ?
        ORDER BY r.created_at DESC
    """, (session["user_id"],))
    reservas = cur.fetchall()
    conn.close()

    return render_template("tienda/mis_reservas.html",
                           reservas=reservas,
                           combustible_labels=_COMBUSTIBLE_LABELS,
                           estado_labels=_ESTADO_LABELS,
                           estado_badge=_ESTADO_BADGE)


# ── Panel admin de reservas ────────────────────────────────────────────────────

@tienda_bp.route("/admin")
def admin():
    if "usuario" not in session or session.get("rol") not in _ROLES_STAFF:
        return redirect("/login")

    filtro_estado = request.args.get("estado", "pendiente")
    filtro_gasolinera = request.args.get("gasolinera_id", "")
    filtro_fecha = request.args.get("fecha", "")

    conditions = []
    params = []
    if filtro_estado:
        conditions.append("r.estado = ?")
        params.append(filtro_estado)
    if filtro_gasolinera:
        conditions.append("r.gasolinera_id = ?")
        params.append(filtro_gasolinera)
    if filtro_fecha:
        conditions.append("DATE(r.created_at) = ?")
        params.append(filtro_fecha)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado='activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()

    cur.execute(f"""
        SELECT r.*, g.nombre AS gasolinera_nombre,
               u.nombre AS cliente_nombre, u.email AS cliente_email
        FROM reservas_tienda r
        JOIN gasolineras g ON g.id = r.gasolinera_id
        JOIN usuarios u ON u.id = r.usuario_id
        {where}
        ORDER BY r.created_at DESC
    """, params)
    reservas = cur.fetchall()
    conn.close()

    return render_template("tienda/admin.html",
                           reservas=reservas,
                           gasolineras=gasolineras,
                           combustible_labels=_COMBUSTIBLE_LABELS,
                           estado_labels=_ESTADO_LABELS,
                           estado_badge=_ESTADO_BADGE,
                           filtro=filtro_estado,
                           filtro_gasolinera=filtro_gasolinera,
                           filtro_fecha=filtro_fecha)


# ── APIs admin ─────────────────────────────────────────────────────────────────

@tienda_bp.route("/api/<int:rid>/aprobar", methods=["POST"])
def api_aprobar(rid):
    if "usuario" not in session or session.get("rol") not in ("admin", "pm"):
        return jsonify({"error": "Sin permiso"}), 403

    tarjeta_id_manual = request.form.get("tarjeta_id", "").strip() or None

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.estado, r.gasolinera_id, r.tipo_combustible, r.litros_solicitados
        FROM reservas_tienda r WHERE r.id = ?
    """, (rid,))
    reserva = cur.fetchone()

    if not reserva or reserva["estado"] != "pendiente":
        conn.close()
        return jsonify({"error": "Reserva no encontrada o no está pendiente"}), 400

    litros = float(reserva["litros_solicitados"])
    gasolinera_id = reserva["gasolinera_id"]
    tipo_combustible = reserva["tipo_combustible"]

    if tarjeta_id_manual:
        cur.execute("""
            SELECT id FROM tarjetas
            WHERE id=? AND gasolinera_id=? AND tipo_combustible=? AND estado='activa'
        """, (tarjeta_id_manual, gasolinera_id, tipo_combustible))
        t = cur.fetchone()
        if not t:
            conn.close()
            return jsonify({"error": "Tarjeta no válida para esta reserva"}), 400
        tarjeta_id = t["id"]
    else:
        cur.execute("""
            SELECT id, saldo_usable_l FROM tarjetas
            WHERE gasolinera_id=? AND tipo_combustible=? AND estado='activa'
              AND saldo_usable_l >= ?
            ORDER BY saldo_usable_l ASC
            LIMIT 1
        """, (gasolinera_id, tipo_combustible, litros))
        t = cur.fetchone()

        if not t:
            cur.execute("""
                SELECT id, numero_parcial, saldo_usable_l FROM tarjetas
                WHERE gasolinera_id=? AND tipo_combustible=? AND estado='activa'
                ORDER BY saldo_usable_l DESC
            """, (gasolinera_id, tipo_combustible))
            tarjetas = cur.fetchall()
            conn.close()
            return jsonify({
                "necesita_tarjeta": True,
                "litros": litros,
                "tarjetas": [{"id": t2["id"], "numero": t2["numero_parcial"],
                               "saldo": float(t2["saldo_usable_l"])} for t2 in tarjetas],
            })
        tarjeta_id = t["id"]

    token = str(uuid.uuid4())
    qr_b64 = _generar_qr_b64(token)

    cur.execute("""
        UPDATE reservas_tienda
        SET estado='aprobada', qr_token=?, qr_imagen_b64=?, aprobado_por=?,
            tarjeta_id=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (token, qr_b64, session["user_id"], tarjeta_id, rid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "token": token})


@tienda_bp.route("/api/<int:rid>/cancelar", methods=["POST"])
def api_cancelar(rid):
    if "usuario" not in session or session.get("rol") not in ("admin", "pm"):
        return jsonify({"error": "Sin permiso"}), 403

    motivo = request.form.get("motivo", "").strip() or None

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reservas_tienda
        SET estado='cancelada', motivo_cancelacion=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND estado IN ('pendiente', 'aprobada')
    """, (motivo, rid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ── Mis vehículos (cliente) ────────────────────────────────────────────────────

@tienda_bp.route("/mis-vehiculos/")
def mis_vehiculos():
    redir = _requiere_cliente()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM vehiculos_tienda WHERE usuario_id=? ORDER BY activo DESC, created_at DESC
    """, (session["user_id"],))
    vehiculos = cur.fetchall()
    conn.close()

    return render_template("tienda/mis_vehiculos.html",
                           vehiculos=vehiculos,
                           combustible_labels=_COMBUSTIBLE_LABELS)


@tienda_bp.route("/mis-vehiculos/crear", methods=["POST"])
def mis_vehiculos_crear():
    redir = _requiere_cliente()
    if redir:
        return redir

    placa = request.form.get("placa", "").strip().upper()
    marca = request.form.get("marca", "").strip() or None
    modelo = request.form.get("modelo", "").strip() or None
    anio_str = request.form.get("anio", "").strip()
    color = request.form.get("color", "").strip() or None
    tipo_combustible = request.form.get("tipo_combustible", "").strip() or None

    if not placa:
        return redirect("/tienda/mis-vehiculos/?error=Placa+requerida")

    try:
        anio = int(anio_str) if anio_str else None
    except ValueError:
        anio = None

    conn = conectar()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO vehiculos_tienda (usuario_id, placa, marca, modelo, anio, color, tipo_combustible)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(usuario_id, placa) DO UPDATE SET
                marca=excluded.marca, modelo=excluded.modelo, anio=excluded.anio,
                color=excluded.color, tipo_combustible=excluded.tipo_combustible,
                updated_at=CURRENT_TIMESTAMP
        """, (session["user_id"], placa, marca, modelo, anio, color, tipo_combustible))
        conn.commit()
    except Exception:
        conn.rollback()
    conn.close()
    return redirect("/tienda/mis-vehiculos/?ok=1")


@tienda_bp.route("/mis-vehiculos/<int:vid>/toggle", methods=["POST"])
def mis_vehiculos_toggle(vid):
    redir = _requiere_cliente()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT activo FROM vehiculos_tienda WHERE id=? AND usuario_id=?",
                (vid, session["user_id"]))
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE vehiculos_tienda SET activo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (0 if row["activo"] else 1, vid))
        conn.commit()
    conn.close()
    return redirect("/tienda/mis-vehiculos/")


@tienda_bp.route("/mis-vehiculos/importar", methods=["POST"])
def mis_vehiculos_importar():
    redir = _requiere_cliente()
    if redir:
        return redir

    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename.endswith((".xlsx", ".xls")):
        return redirect("/tienda/mis-vehiculos/?error=Archivo+Excel+requerido")

    try:
        import openpyxl
        wb = openpyxl.load_workbook(archivo)
        ws = wb.active
        conn = conectar()
        cur = conn.cursor()
        importados = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            placa = str(row[0]).strip().upper()
            marca = str(row[1]).strip() if len(row) > 1 and row[1] else None
            modelo = str(row[2]).strip() if len(row) > 2 and row[2] else None
            try:
                anio = int(row[3]) if len(row) > 3 and row[3] else None
            except (ValueError, TypeError):
                anio = None
            color = str(row[4]).strip() if len(row) > 4 and row[4] else None
            tc = str(row[5]).strip() if len(row) > 5 and row[5] else None
            cur.execute("""
                INSERT INTO vehiculos_tienda (usuario_id, placa, marca, modelo, anio, color, tipo_combustible)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(usuario_id, placa) DO UPDATE SET
                    marca=excluded.marca, modelo=excluded.modelo, anio=excluded.anio,
                    color=excluded.color, tipo_combustible=excluded.tipo_combustible,
                    updated_at=CURRENT_TIMESTAMP
            """, (session["user_id"], placa, marca, modelo, anio, color, tc))
            importados += 1
        conn.commit()
        conn.close()
        return redirect(f"/tienda/mis-vehiculos/?ok={importados}")
    except Exception:
        return redirect("/tienda/mis-vehiculos/?error=Error+al+importar+el+archivo")


# ── Util QR ────────────────────────────────────────────────────────────────────

def _generar_qr_b64(token):
    try:
        import qrcode
        url = f"https://mercatoria-fuel.onrender.com/qr/{token}"
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None
