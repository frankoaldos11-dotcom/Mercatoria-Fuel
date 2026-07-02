from flask import Blueprint, render_template, request, redirect, session, jsonify
from database import conectar
from utils.auth import requiere_rol
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS

configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")

_ROLES_ADMIN = ["admin"]

_PARAMS_LABELS = {
    "compra_minima_litros": {
        "label": "Compra mínima por habilitación (litros)",
        "hint": "El mínimo de litros que debe tener una habilitación para ser aceptada.",
        "tipo": "numero",
    },
}


@configuracion_bp.route("/", methods=["GET", "POST"])
def index():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    error = None
    ok = False

    if request.method == "POST":
        for clave in _PARAMS_LABELS:
            valor = request.form.get(clave, "").strip()
            if valor:
                cur.execute(
                    "UPDATE configuracion SET valor = ?, updated_at = CURRENT_TIMESTAMP WHERE clave = ?",
                    (valor, clave)
                )
        conn.commit()
        conn.close()
        return redirect("/configuracion/?ok=1")

    cur.execute("SELECT clave, valor FROM configuracion")
    rows = cur.fetchall()
    config = {r["clave"]: r["valor"] for r in rows}

    cur.execute("""
        SELECT pc.id, pc.gasolinera_id, pc.tipo_combustible,
               pc.precio_usd_por_litro, pc.activo,
               g.nombre AS gasolinera_nombre
        FROM precios_combustible pc
        JOIN gasolineras g ON g.id = pc.gasolinera_id
        ORDER BY g.nombre ASC, pc.tipo_combustible ASC
    """)
    precios = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado='activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()

    conn.close()

    return render_template(
        "configuracion/index.html",
        config=config,
        params_labels=_PARAMS_LABELS,
        precios=precios,
        gasolineras=gasolineras,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        tipos_combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        error=error,
        ok=ok,
    )


@configuracion_bp.route("/precios/guardar", methods=["POST"])
def precios_guardar():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    gid = request.form.get("gasolinera_id", "").strip()
    tc = request.form.get("tipo_combustible", "").strip()
    precio_str = request.form.get("precio_usd_por_litro", "0").strip()

    try:
        precio = float(precio_str.replace(",", "."))
    except ValueError:
        precio = 0.0

    if not gid or not tc or precio <= 0:
        return redirect("/configuracion/?error=Datos+inválidos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO precios_combustible (gasolinera_id, tipo_combustible, precio_usd_por_litro, activo)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(gasolinera_id, tipo_combustible)
        DO UPDATE SET precio_usd_por_litro=excluded.precio_usd_por_litro,
                      activo=1, updated_at=CURRENT_TIMESTAMP
    """, (gid, tc, precio))
    conn.commit()
    conn.close()
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/<int:pid>/toggle", methods=["POST"])
def precios_toggle(pid):
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT activo FROM precios_combustible WHERE id=?", (pid,))
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE precios_combustible SET activo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (0 if row["activo"] else 1, pid))
        conn.commit()
    conn.close()
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/<int:pid>/eliminar", methods=["POST"])
def precios_eliminar(pid):
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("DELETE FROM precios_combustible WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/<int:pid>/editar", methods=["POST"])
def precios_editar(pid):
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return jsonify({"error": "Sin permiso"}), 403

    precio_str = request.form.get("precio_usd_por_litro", "0").strip()
    try:
        precio = float(precio_str.replace(",", "."))
    except ValueError:
        precio = 0.0

    if precio <= 0:
        return jsonify({"error": "Precio inválido"}), 400

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE precios_combustible SET precio_usd_por_litro=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
    """, (precio, pid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "precio": f"{precio:.4f}"})
