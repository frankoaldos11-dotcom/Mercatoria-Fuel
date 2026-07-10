import logging

from flask import Blueprint, render_template, request, redirect, session, jsonify

from database import conectar
from utils import mailer
from utils.auth import requiere_staff, requiere_rol
from utils.constants import ROLES_ADMIN_PM

logger = logging.getLogger(__name__)

mensajes_bp = Blueprint("mensajes", __name__, url_prefix="/mensajes")

_MODOS_DESTINATARIO = ("todos", "filtro", "manual")
_FILTROS_ESTADO = ("activo", "verificado")


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


# ── Mensajería masiva ────────────────────────────────────────────────────────

def _resolver_destinatarios(cur, masivo_id, modo, filtro_estado):
    """Returns rows (id, nombre, email, email_verificado) for the base recipient set."""
    if modo == "todos":
        cur.execute("SELECT id, nombre, email, email_verificado FROM usuarios WHERE rol='cliente'")
    elif modo == "filtro" and filtro_estado == "activo":
        cur.execute("SELECT id, nombre, email, email_verificado FROM usuarios WHERE rol='cliente' AND activo=1")
    elif modo == "filtro" and filtro_estado == "verificado":
        cur.execute("SELECT id, nombre, email, email_verificado FROM usuarios WHERE rol='cliente' AND email_verificado=1")
    elif modo == "manual":
        cur.execute("""
            SELECT u.id, u.nombre, u.email, u.email_verificado
            FROM usuarios u
            JOIN mensajes_masivos_destinatarios d ON d.usuario_id = u.id
            WHERE d.masivo_id = ?
        """, (masivo_id,))
    else:
        return []
    return cur.fetchall()


def _enviar_masivo(masivo_id, aprobado_por_id):
    """Resolves recipients, sends email to the verified subset, optionally
    records an in-app copy for everyone, and persists the summary.

    Never raises — an individual SMTP failure never aborts the batch.
    """
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT asunto, cuerpo, modo_destinatario, filtro_estado, incluir_inapp
        FROM mensajes_masivos WHERE id=?
    """, (masivo_id,))
    masivo = cur.fetchone()
    if not masivo:
        conn.close()
        return

    destinatarios = _resolver_destinatarios(cur, masivo_id, masivo["modo_destinatario"],
                                             masivo["filtro_estado"])
    conn.close()

    verificados = [d for d in destinatarios if d["email_verificado"]]
    no_verificados = [d for d in destinatarios if not d["email_verificado"]]

    total_enviados = 0
    total_fallidos = 0
    for d in verificados:
        try:
            ok = mailer.masivo_email(d["nombre"], d["email"], d["id"],
                                      masivo["asunto"], masivo["cuerpo"])
        except Exception:
            logger.error("Error enviando masivo #%s a usuario #%s", masivo_id, d["id"], exc_info=True)
            ok = False
        if ok:
            total_enviados += 1
        else:
            total_fallidos += 1

    if masivo["incluir_inapp"]:
        for d in destinatarios:
            try:
                mailer.registrar_mensaje_inapp(d["email"], masivo["asunto"], masivo["cuerpo"], d["id"])
            except Exception:
                logger.error("Error registrando in-app de masivo #%s para usuario #%s",
                             masivo_id, d["id"], exc_info=True)

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE mensajes_masivos
        SET estado='enviado', aprobado_por=?, enviado_at=CURRENT_TIMESTAMP,
            updated_at=CURRENT_TIMESTAMP, total_destinatarios=?, total_enviados=?,
            total_excluidos_no_verificado=?, total_fallidos=?
        WHERE id=?
    """, (aprobado_por_id, len(destinatarios), total_enviados,
          len(no_verificados), total_fallidos, masivo_id))
    conn.commit()
    conn.close()


@mensajes_bp.route("/masivos/nuevo", methods=["GET", "POST"])
def masivos_nuevo():
    redir = requiere_rol(*ROLES_ADMIN_PM)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, email, activo, email_verificado FROM usuarios
        WHERE rol='cliente' ORDER BY nombre ASC
    """)
    clientes = cur.fetchall()

    error = None

    if request.method == "POST":
        asunto = request.form.get("asunto", "").strip()
        cuerpo = request.form.get("cuerpo", "").strip()
        modo = request.form.get("modo_destinatario", "").strip()
        filtro_estado = request.form.get("filtro_estado", "").strip() or None
        incluir_inapp = request.form.get("incluir_inapp") == "on"
        destinatarios_manual = request.form.getlist("destinatarios_manual")

        if not asunto:
            error = "El asunto es obligatorio."
        elif not cuerpo:
            error = "El contenido del mensaje es obligatorio."
        elif modo not in _MODOS_DESTINATARIO:
            error = "Selecciona a quién va dirigido el mensaje."
        elif modo == "filtro" and filtro_estado not in _FILTROS_ESTADO:
            error = "Selecciona el estado del filtro."
        elif modo == "manual" and not destinatarios_manual:
            error = "Selecciona al menos un cliente."

        if not error:
            rol = session.get("rol")
            cur.execute("""
                INSERT INTO mensajes_masivos
                    (asunto, cuerpo, modo_destinatario, filtro_estado, incluir_inapp,
                     estado, autor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (asunto, cuerpo, modo, filtro_estado if modo == "filtro" else None,
                  1 if incluir_inapp else 0, "pendiente", session["user_id"]))
            nuevo_id = cur.lastrowid

            if modo == "manual":
                for uid in destinatarios_manual:
                    cur.execute("""
                        INSERT INTO mensajes_masivos_destinatarios (masivo_id, usuario_id)
                        VALUES (?, ?)
                    """, (nuevo_id, uid))

            conn.commit()
            conn.close()

            if rol == "admin":
                try:
                    _enviar_masivo(nuevo_id, session["user_id"])
                except Exception:
                    logger.error("Error enviando masivo #%s", nuevo_id, exc_info=True)

            return redirect(f"/mensajes/masivos/{nuevo_id}?ok=1")

    conn.close()
    return render_template("mensajes/masivos_nuevo.html",
                           clientes=clientes, error=error, form=request.form)


@mensajes_bp.route("/masivos")
def masivos_listado():
    redir = requiere_rol(*ROLES_ADMIN_PM)
    if redir:
        return redir

    filtro = request.args.get("estado", "").strip()
    conn = conectar()
    cur = conn.cursor()
    if filtro:
        cur.execute("""
            SELECT mm.*, u.nombre AS autor_nombre
            FROM mensajes_masivos mm
            JOIN usuarios u ON u.id = mm.autor_id
            WHERE mm.estado = ?
            ORDER BY mm.created_at DESC
        """, (filtro,))
    else:
        cur.execute("""
            SELECT mm.*, u.nombre AS autor_nombre
            FROM mensajes_masivos mm
            JOIN usuarios u ON u.id = mm.autor_id
            ORDER BY mm.created_at DESC
        """)
    lista = cur.fetchall()
    conn.close()
    return render_template("mensajes/masivos_listado.html", lista=lista, filtro=filtro)


@mensajes_bp.route("/masivos/<int:mid>")
def masivos_detalle(mid):
    redir = requiere_rol(*ROLES_ADMIN_PM)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT mm.*, u.nombre AS autor_nombre, ap.nombre AS aprobado_por_nombre
        FROM mensajes_masivos mm
        JOIN usuarios u ON u.id = mm.autor_id
        LEFT JOIN usuarios ap ON ap.id = mm.aprobado_por
        WHERE mm.id = ?
    """, (mid,))
    masivo = cur.fetchone()

    if not masivo:
        conn.close()
        return redirect("/mensajes/masivos")

    destinatarios_manual = []
    if masivo["modo_destinatario"] == "manual":
        cur.execute("""
            SELECT u.nombre, u.email FROM usuarios u
            JOIN mensajes_masivos_destinatarios d ON d.usuario_id = u.id
            WHERE d.masivo_id = ?
        """, (mid,))
        destinatarios_manual = cur.fetchall()

    conn.close()
    return render_template("mensajes/masivos_detalle.html",
                           masivo=masivo, destinatarios_manual=destinatarios_manual)


@mensajes_bp.route("/masivos/<int:mid>/aprobar", methods=["POST"])
def masivos_aprobar(mid):
    redir = requiere_rol("admin")
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM mensajes_masivos WHERE id=?", (mid,))
    masivo = cur.fetchone()
    conn.close()

    if not masivo or masivo["estado"] != "pendiente":
        return redirect("/mensajes/masivos?access_error=El+mensaje+no+esta+pendiente+de+aprobacion")

    try:
        _enviar_masivo(mid, session["user_id"])
    except Exception:
        logger.error("Error aprobando/enviando masivo #%s", mid, exc_info=True)

    return redirect(f"/mensajes/masivos/{mid}?ok=1")


@mensajes_bp.route("/masivos/<int:mid>/rechazar", methods=["POST"])
def masivos_rechazar(mid):
    redir = requiere_rol("admin")
    if redir:
        return jsonify({"error": "No autorizado"}), 401

    motivo = request.form.get("motivo", "").strip()
    if not motivo:
        return jsonify({"ok": False, "error": "El motivo de rechazo es obligatorio."})

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE mensajes_masivos
        SET estado='rechazado', motivo_rechazo=?, aprobado_por=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=? AND estado='pendiente'
    """, (motivo, session["user_id"], mid))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})
