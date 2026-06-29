from flask import Blueprint, render_template, request
from utils.auth import requiere_login

modulos_bp = Blueprint("modulos", __name__)


@modulos_bp.route("/configuracion")
@modulos_bp.route("/usuarios")
def placeholder():
    redir = requiere_login()
    if redir:
        return redir

    path = request.path.strip("/")
    titulo_map = {
        "configuracion": "Configuración",
        "usuarios": "Usuarios",
    }
    titulo = titulo_map.get(path, path.capitalize())
    return render_template("modulos/placeholder.html", titulo=titulo, path=path)
