from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.auth import requiere_rol

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
    conn.close()

    return render_template(
        "configuracion/index.html",
        config=config,
        params_labels=_PARAMS_LABELS,
        error=error,
    )
