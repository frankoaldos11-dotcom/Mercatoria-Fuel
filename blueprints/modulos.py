from flask import Blueprint, render_template, session, redirect

modulos_bp = Blueprint("modulos", __name__)

_PLACEHOLDERS = [
    ("/depositos",      "Depósitos",          "bi-archive"),
    ("/clientes",       "Clientes",           "bi-buildings"),
    ("/vehiculos",      "Vehículos y Choferes","bi-truck"),
    ("/tarjetas",       "Tarjetas",           "bi-credit-card-2-front"),
    ("/habilitaciones", "Habilitaciones",     "bi-toggle-on"),
    ("/despachos",      "Despachos",          "bi-box-arrow-right"),
    ("/conciliacion",   "Conciliación",       "bi-check2-square"),
    ("/reportes",       "Reportes",           "bi-bar-chart-line"),
    ("/configuracion",  "Configuración",      "bi-sliders"),
    ("/usuarios",       "Usuarios",           "bi-people"),
]


def _requiere_login():
    return "usuario" not in session


@modulos_bp.route("/depositos")
@modulos_bp.route("/clientes")
@modulos_bp.route("/vehiculos")
@modulos_bp.route("/tarjetas")
@modulos_bp.route("/habilitaciones")
@modulos_bp.route("/despachos")
@modulos_bp.route("/conciliacion")
@modulos_bp.route("/reportes")
@modulos_bp.route("/configuracion")
@modulos_bp.route("/usuarios")
def placeholder():
    if _requiere_login():
        return redirect("/login")

    from flask import request
    path = request.path.strip("/")
    titulo_map = {
        "depositos":      "Depósitos",
        "clientes":       "Clientes",
        "vehiculos":      "Vehículos y Choferes",
        "tarjetas":       "Tarjetas",
        "habilitaciones": "Habilitaciones",
        "despachos":      "Despachos",
        "conciliacion":   "Conciliación",
        "reportes":       "Reportes",
        "configuracion":  "Configuración",
        "usuarios":       "Usuarios",
    }
    titulo = titulo_map.get(path, path.capitalize())
    return render_template("modulos/placeholder.html", titulo=titulo, path=path)


@modulos_bp.route("/tl38")
def tl38():
    if _requiere_login():
        return redirect("/login")
    return render_template("modulos/tl38.html")
