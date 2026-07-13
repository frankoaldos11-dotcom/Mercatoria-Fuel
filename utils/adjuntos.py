import os

from werkzeug.utils import secure_filename

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def foto_valida(file):
    """Valida solo la extensión, sin leer el contenido ni tocar la DB."""
    if not file or not file.filename:
        return False
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    return ext in _ALLOWED_EXT


def guardar_adjunto(cur, origen_tipo, origen_id, categoria, file):
    """Lee el binario en memoria e inserta el adjunto con el cursor de la
    transacción en curso (mismo commit/rollback que el registro que lo origina).
    Devuelve la URL de servido, o None si el archivo no viene o el formato no es válido.
    """
    if not foto_valida(file):
        return None
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    contenido = file.read()
    if not contenido:
        return None
    cur.execute("""
        INSERT INTO adjuntos (origen_tipo, origen_id, categoria, nombre_original, mime_type, contenido)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (origen_tipo, origen_id, categoria, secure_filename(file.filename), _MIME_BY_EXT[ext], contenido))
    return f"/adjuntos/{cur.lastrowid}"
