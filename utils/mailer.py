import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from database import conectar

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds — fail fast if SMTP server hangs


def _smtp_cfg():
    host = os.environ.get("SMTP_HOST", "").strip()
    port = os.environ.get("SMTP_PORT", "465").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    if not (host and user and password):
        return None
    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password,
        "from_addr": f"Mercatoria Fuel <{user}>",
    }


def enviar_email(destinatario, asunto, cuerpo_html, tipo="general",
                 usuario_id=None, cliente_id=None):
    """Send email and record the attempt in mensajes table.

    Never raises. Returns True if sent, False otherwise.
    """
    estado = "enviado"
    error_text = None

    cfg = _smtp_cfg()
    if cfg is None:
        estado = "fallido"
        error_text = "SMTP no configurado (SMTP_HOST, SMTP_USER o SMTP_PASSWORD faltantes)"
        logger.warning("Email no enviado — SMTP no configurado. dest=%s", destinatario)
    else:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = asunto
            msg["From"] = cfg["from_addr"]
            msg["To"] = destinatario
            msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=_TIMEOUT) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_addr"], [destinatario], msg.as_string())

        except Exception as exc:
            estado = "fallido"
            error_text = str(exc)
            logger.error("Error enviando email a %s: %s", destinatario, exc, exc_info=True)

    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO mensajes
               (destinatario, asunto, cuerpo, tipo, estado, error, usuario_id, cliente_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (destinatario, asunto, cuerpo_html, tipo, estado, error_text,
             usuario_id, cliente_id),
        )
        conn.commit()
        conn.close()
    except Exception as db_exc:
        logger.error("Error registrando mensaje en BD: %s", db_exc, exc_info=True)

    return estado == "enviado"


def bienvenida(nombre, email, usuario_id):
    """Send welcome email to a newly registered client."""
    asunto = "Bienvenido a Mercatoria Fuel — tu cuenta ha sido creada"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Hola <strong>{nombre}</strong>,</p>
<p>Tu cuenta en <strong>Mercatoria Fuel</strong> ha sido creada correctamente.</p>
<p>Un administrador debe activarla antes de que puedas iniciar sesión.
   Recibirás acceso cuando tu cuenta sea aprobada.</p>
<p style="color:#64748b;font-size:13px;">Mercatoria Fuel — Sistema de control de combustible</p>
</body></html>"""
    return enviar_email(email, asunto, cuerpo, tipo="bienvenida", usuario_id=usuario_id)
