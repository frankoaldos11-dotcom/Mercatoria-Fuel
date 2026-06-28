from flask import Blueprint, render_template, request
from utils.auth import requiere_login

modulos_bp = Blueprint("modulos", __name__)


@modulos_bp.route("/habilitaciones")
@modulos_bp.route("/despachos")
@modulos_bp.route("/conciliacion")
@modulos_bp.route("/reportes")
@modulos_bp.route("/configuracion")
@modulos_bp.route("/usuarios")
def placeholder():
    redir = requiere_login()
    if redir:
        return redir

    path = request.path.strip("/")
    titulo_map = {
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
    redir = requiere_login()
    if redir:
        return redir
    return render_template("modulos/tl38.html")
