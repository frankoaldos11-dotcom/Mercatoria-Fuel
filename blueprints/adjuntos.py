from flask import Blueprint, Response, session, abort

from database import conectar
from utils.auth import requiere_login

adjuntos_bp = Blueprint("adjuntos", __name__, url_prefix="/adjuntos")


def _autorizado(cur, origen_tipo, origen_id):
    if session.get("rol") != "cliente":
        return True

    if origen_tipo == "despacho":
        cur.execute("SELECT cliente_id FROM despachos WHERE id = ?", (origen_id,))
        row = cur.fetchone()
        return bool(row and row["cliente_id"] == session.get("cliente_id"))

    if origen_tipo == "reserva_tienda":
        cur.execute("SELECT usuario_id FROM reservas_tienda WHERE id = ?", (origen_id,))
        row = cur.fetchone()
        return bool(row and row["usuario_id"] == session.get("user_id"))

    return False


@adjuntos_bp.route("/<int:adjunto_id>")
def ver(adjunto_id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT origen_tipo, origen_id, mime_type, contenido
        FROM adjuntos WHERE id = ?
    """, (adjunto_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        abort(404)

    if not _autorizado(cur, row["origen_tipo"], row["origen_id"]):
        conn.close()
        abort(403)

    contenido = bytes(row["contenido"])
    mime_type = row["mime_type"]
    conn.close()
    return Response(contenido, mimetype=mime_type)
