import base64
import logging
import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from database import conectar

logger = logging.getLogger(__name__)

_TIMEOUT = 10  # seconds — fail fast if SMTP server hangs

# Único lugar donde se define qué roles reciben cada tipo de aviso de staff.
_ROLES_POR_AVISO = {
    "reserva_pendiente": ("admin", "puesto_de_mando"),
    "sin_cobertura_saldo": ("admin", "puesto_de_mando"),
    "conciliacion_diferencia": ("admin", "puesto_de_mando"),
    "combustible_sin_distribuir": ("admin", "puesto_de_mando"),
}


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
                 usuario_id=None, cliente_id=None,
                 imagen_inline_b64=None, imagen_cid=None):
    """Send email and record the attempt in mensajes table.

    Never raises. Returns True if sent, False otherwise.

    If imagen_inline_b64 is given (with imagen_cid), it's attached inline
    (Content-ID) so cuerpo_html can reference it as src="cid:<imagen_cid>".
    """
    estado = "enviado"
    error_text = None

    cfg = _smtp_cfg()
    if cfg is None:
        estado = "fallido"
        error_text = "SMTP no configurado (SMTP_HOST, SMTP_USER o SMTP_PASSWORD faltantes)"
        logger.warning("Email no enviado — SMTP no configurado. usuario_id=%s cliente_id=%s",
                       usuario_id, cliente_id)
    else:
        try:
            if imagen_inline_b64 and imagen_cid:
                msg = MIMEMultipart("related")
                alt = MIMEMultipart("alternative")
                alt.attach(MIMEText(cuerpo_html, "html", "utf-8"))
                msg.attach(alt)
                img = MIMEImage(base64.b64decode(imagen_inline_b64))
                img.add_header("Content-ID", f"<{imagen_cid}>")
                img.add_header("Content-Disposition", "inline", filename=f"{imagen_cid}.png")
                msg.attach(img)
            else:
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

            msg["Subject"] = asunto
            msg["From"] = cfg["from_addr"]
            msg["To"] = destinatario

            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=_TIMEOUT) as server:
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_addr"], [destinatario], msg.as_string())

        except Exception as exc:
            estado = "fallido"
            error_text = str(exc)
            logger.error("Error enviando email (usuario_id=%s cliente_id=%s): %s",
                         usuario_id, cliente_id, exc, exc_info=True)

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


_PIE = '<p style="color:#64748b;font-size:13px;">Mercatoria Fuel — Sistema de control de combustible</p>'


def reserva_aprobada(nombre, email, usuario_id, gasolinera, tipo_combustible, litros,
                      qr_token, qr_imagen_b64):
    """Notify a tienda client that their reservation was approved. Includes the
    existing QR (inline + link) — does not generate a new one."""
    asunto = "Tu reserva en Mercatoria Fuel fue aprobada"
    link = f"https://mercatoria-fuel.onrender.com/qr/{qr_token}"
    cid = "qr_reserva"
    imagen_html = (
        f'<p style="text-align:center;"><img src="cid:{cid}" alt="Codigo QR de tu reserva" '
        f'style="max-width:220px;border:1px solid #e2e8f0;border-radius:8px;"/></p>'
        if qr_imagen_b64 else ""
    )
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Hola <strong>{nombre}</strong>,</p>
<p>Tu reserva de <strong>{litros:,.2f} L</strong> de <strong>{tipo_combustible}</strong> en
   <strong>{gasolinera}</strong> ha sido <strong>aprobada</strong>.</p>
{imagen_html}
<p>Presenta este código QR en la gasolinera para completar tu despacho, o consúltalo en la app:<br>
   <a href="{link}">{link}</a></p>
{_PIE}
</body></html>"""
    return enviar_email(
        email, asunto, cuerpo, tipo="reserva_aprobada", usuario_id=usuario_id,
        imagen_inline_b64=qr_imagen_b64 if qr_imagen_b64 else None,
        imagen_cid=cid if qr_imagen_b64 else None,
    )


def reserva_rechazada(nombre, email, usuario_id, motivo):
    """Notify a tienda client that their reservation was rejected/cancelled."""
    asunto = "Tu reserva en Mercatoria Fuel fue rechazada"
    motivo_html = f"<p><strong>Motivo:</strong> {motivo}</p>" if motivo else ""
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Hola <strong>{nombre}</strong>,</p>
<p>Tu reserva en <strong>Mercatoria Fuel</strong> ha sido <strong>rechazada</strong>.</p>
{motivo_html}
{_PIE}
</body></html>"""
    return enviar_email(email, asunto, cuerpo, tipo="reserva_rechazada", usuario_id=usuario_id)


def despacho_completado(nombre, email, usuario_id, gasolinera, tipo_combustible, litros):
    """Notify a tienda client that their dispatch was completed."""
    asunto = "Tu despacho en Mercatoria Fuel fue completado"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Hola <strong>{nombre}</strong>,</p>
<p>Tu despacho de <strong>{litros:,.2f} L</strong> de <strong>{tipo_combustible}</strong> en
   <strong>{gasolinera}</strong> ha sido <strong>completado</strong>.</p>
<p>Gracias por usar Mercatoria Fuel.</p>
{_PIE}
</body></html>"""
    return enviar_email(email, asunto, cuerpo, tipo="despacho_completado", usuario_id=usuario_id)


def _destinatarios_staff(roles):
    conn = conectar()
    cur = conn.cursor()
    placeholders = ",".join("?" for _ in roles)
    cur.execute(
        f"SELECT id, nombre, email FROM usuarios WHERE rol IN ({placeholders}) AND activo=1",
        tuple(roles),
    )
    filas = cur.fetchall()
    conn.close()
    return filas


def notificar_staff(clave_aviso, asunto, cuerpo_html):
    """Resolve recipients by role (see _ROLES_POR_AVISO) and send to each.

    Never raises. Logs and returns quietly if there are no active recipients.
    """
    roles = _ROLES_POR_AVISO.get(clave_aviso, ())
    if not roles:
        logger.warning("Aviso de staff desconocido: %s", clave_aviso)
        return

    try:
        destinatarios = _destinatarios_staff(roles)
    except Exception as exc:
        logger.error("Error consultando destinatarios de staff para %s: %s",
                     clave_aviso, exc, exc_info=True)
        return

    if not destinatarios:
        logger.warning("Sin destinatarios activos para aviso de staff %s (roles=%s)",
                        clave_aviso, roles)
        return

    for u in destinatarios:
        enviar_email(u["email"], asunto, cuerpo_html, tipo=clave_aviso, usuario_id=u["id"])


def staff_reserva_pendiente(cliente_nombre, gasolinera, tipo_combustible, litros, reserva_id):
    asunto = f"Nueva reserva pendiente #{reserva_id} — {gasolinera}"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Nueva reserva pendiente de aprobación:</p>
<ul>
<li><strong>Cliente:</strong> {cliente_nombre}</li>
<li><strong>Gasolinera:</strong> {gasolinera}</li>
<li><strong>Combustible:</strong> {tipo_combustible}</li>
<li><strong>Litros:</strong> {litros:,.2f} L</li>
</ul>
{_PIE}
</body></html>"""
    notificar_staff("reserva_pendiente", asunto, cuerpo)


def staff_sin_cobertura_saldo(gasolinera, tipo_combustible, detalle):
    asunto = f"Gasolinera sin cobertura de saldo — {gasolinera}"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p><strong>{gasolinera}</strong> no tiene cobertura de saldo suficiente para
   <strong>{tipo_combustible}</strong>.</p>
<p>{detalle}</p>
{_PIE}
</body></html>"""
    notificar_staff("sin_cobertura_saldo", asunto, cuerpo)


def staff_conciliacion_diferencia(gasolinera, fecha, diferencia_l, diferencia_pct, conciliacion_id):
    asunto = f"Conciliación con diferencias #{conciliacion_id} — {gasolinera}"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>La conciliación de <strong>{gasolinera}</strong> del {fecha} presenta una diferencia que
   supera la tolerancia permitida:</p>
<ul>
<li><strong>Diferencia:</strong> {diferencia_l:,.2f} L ({diferencia_pct:.2%})</li>
</ul>
{_PIE}
</body></html>"""
    notificar_staff("conciliacion_diferencia", asunto, cuerpo)


def staff_combustible_sin_distribuir(gasolinera, tipo_combustible, litros_recibidos, transferencia_id):
    asunto = f"Combustible sin distribuir #{transferencia_id} — {gasolinera}"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Llegó una transferencia de <strong>{litros_recibidos:,.2f} L</strong> de
   <strong>{tipo_combustible}</strong> a <strong>{gasolinera}</strong> que aún no ha sido
   distribuida a tarjetas.</p>
{_PIE}
</body></html>"""
    notificar_staff("combustible_sin_distribuir", asunto, cuerpo)


def verificacion_email(nombre, email, usuario_id, token, codigo):
    """Send email verification link (primary) + fallback code to a tienda client."""
    asunto = "Verifica tu correo — Mercatoria Fuel"
    link = f"https://mercatoria-fuel.onrender.com/tienda/verificar-email/{token}"
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Hola <strong>{nombre}</strong>,</p>
<p>Para poder confirmar reservas en <strong>Mercatoria Fuel</strong> necesitas verificar tu correo.</p>
<p style="text-align:center;margin:24px 0;">
   <a href="{link}" style="background:#E86A2C;color:#fff;padding:12px 24px;border-radius:8px;
      text-decoration:none;font-weight:bold;">Verificar mi correo</a>
</p>
<p>Si el botón no funciona, copia este enlace en tu navegador:<br>
   <a href="{link}">{link}</a></p>
<p>¿No puedes usar el enlace? Ingresa este código dentro de la app:
   <strong style="font-size:1.3em;letter-spacing:2px;">{codigo}</strong></p>
<p style="color:#64748b;font-size:13px;">Este enlace y código vencen en 24 horas.</p>
{_PIE}
</body></html>"""
    return enviar_email(email, asunto, cuerpo, tipo="verificacion_email", usuario_id=usuario_id)


def masivo_email(nombre, email, usuario_id, asunto, cuerpo_masivo):
    """Send a staff-composed bulk email to a client. Wraps the composed body
    in the standard envelope and reuses enviar_email() — never raises."""
    cuerpo = f"""<html><body style="font-family:sans-serif;color:#1e293b;line-height:1.6;">
<p>Hola <strong>{nombre}</strong>,</p>
{cuerpo_masivo}
{_PIE}
</body></html>"""
    return enviar_email(email, asunto, cuerpo, tipo="masivo", usuario_id=usuario_id)


def registrar_mensaje_inapp(destinatario_email, asunto, cuerpo_html, usuario_id):
    """Record an in-app copy of a bulk message in the mensajes table.

    There is no external channel here (no SMTP), so there is nothing that can
    fail besides the DB write itself — logs and returns quietly on error.
    """
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO mensajes
               (destinatario, asunto, cuerpo, tipo, estado, usuario_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (destinatario_email, asunto, cuerpo_html, "masivo_inapp", "enviado", usuario_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.error("Error registrando mensaje in-app para usuario #%s", usuario_id, exc_info=True)
