from flask import Blueprint, render_template

from database import conectar
from utils.auth import requiere_staff

mensajes_bp = Blueprint("mensajes", __name__, url_prefix="/mensajes")


@mensajes_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.id, m.destinatario, m.asunto, m.tipo, m.estado, m.error,
               m.created_at, u.nombre AS usuario_nombre
        FROM mensajes m
        LEFT JOIN usuarios u ON u.id = m.usuario_id
        ORDER BY m.created_at DESC
        LIMIT 200
    """)
    lista = cur.fetchall()
    conn.close()
    return render_template("mensajes/listado.html", lista=lista)
