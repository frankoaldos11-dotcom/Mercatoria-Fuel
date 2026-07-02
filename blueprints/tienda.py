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

    cur.execute("SELECT valor FROM configuracion WHERE clave = 'compra_minima_litros'")
    row_min = cur.fetchone()
    compra_minima = float(row_min["valor"]) if row_min else 0.0

    error = None

    if request.method == "POST":
        gid = request.form.get("gasolinera_id", "").strip()
        tc = request.form.get("tipo_combustible", "").strip()
        litros_str = request.form.get("litros", "0").strip()
        desc_vehiculo = request.form.get("descripcion_vehiculo", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        try:
            litros = float(litros_str.replace(",", "."))
        except ValueError:
            litros = 0.0

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
                     precio_usd_por_litro, precio_total_usd, descripcion_vehiculo, observaciones)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (session["user_id"], gid, tc, litros, precio_unitario, precio_total,
                  desc_vehiculo or None, observaciones or None))
            nueva_id = cur.lastrowid
            conn.commit()
            conn.close()
            return redirect(f"/tienda/confirmacion/{nueva_id}")

    conn.close()

    return render_template("tienda/reservar.html",
                           productos=productos,
                           gasolineras=gasolineras,
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

    filtro = request.args.get("estado", "pendiente")
    params = []
    where = ""
    if filtro:
        where = "WHERE r.estado = ?"
        params.append(filtro)

    conn = conectar()
    cur = conn.cursor()
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
                           combustible_labels=_COMBUSTIBLE_LABELS,
                           estado_labels=_ESTADO_LABELS,
                           estado_badge=_ESTADO_BADGE,
                           filtro=filtro)


# ── APIs admin ─────────────────────────────────────────────────────────────────

@tienda_bp.route("/api/<int:rid>/aprobar", methods=["POST"])
def api_aprobar(rid):
    if "usuario" not in session or session.get("rol") not in ("admin", "pm"):
        return jsonify({"error": "Sin permiso"}), 403

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM reservas_tienda WHERE id = ?", (rid,))
    row = cur.fetchone()

    if not row or row["estado"] != "pendiente":
        conn.close()
        return jsonify({"error": "Reserva no encontrada o no está pendiente"}), 400

    token = str(uuid.uuid4())
    qr_b64 = _generar_qr_b64(token)

    cur.execute("""
        UPDATE reservas_tienda
        SET estado='aprobada', qr_token=?, qr_imagen_b64=?, aprobado_por=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (token, qr_b64, session["user_id"], rid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "token": token})


@tienda_bp.route("/api/<int:rid>/cancelar", methods=["POST"])
def api_cancelar(rid):
    if "usuario" not in session or session.get("rol") not in ("admin", "pm"):
        return jsonify({"error": "Sin permiso"}), 403

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE reservas_tienda
        SET estado='cancelada', updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND estado IN ('pendiente', 'aprobada')
    """, (rid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


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
