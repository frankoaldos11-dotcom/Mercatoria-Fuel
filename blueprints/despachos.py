import os
import uuid
from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, session, current_app
from werkzeug.utils import secure_filename

from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE_LABELS, ESTADOS_HABILITACION_LABELS
from utils.auth import requiere_login

despachos_bp = Blueprint("despachos", __name__, url_prefix="/despachos")

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def _save_photo(file, subfolder):
    if not file or not file.filename:
        return None
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in _ALLOWED_EXT:
        return None
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_root = current_app.config.get("UPLOAD_FOLDER",
                                         os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                       "..", "static", "uploads"))
    dest = os.path.join(upload_root, subfolder, filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    file.save(dest)
    return f"/static/uploads/{subfolder}/{filename}"


# ── Listado ───────────────────────────────────────────────────────────────────

@despachos_bp.route("/")
def listado():
    redir = requiere_login()
    if redir:
        return redir

    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_cliente = request.args.get("cliente_id", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()
    filtro_estado = request.args.get("estado", "").strip()

    condiciones = []
    params = []

    # Para operador_gasolinera: restringir siempre a su gasolinera asignada
    if session.get("rol") == "operador_gasolinera":
        condiciones.append("d.gasolinera_id = ?")
        params.append(session.get("gasolinera_id"))
    elif filtro_gasolinera:
        condiciones.append("d.gasolinera_id = ?")
        params.append(filtro_gasolinera)
    if filtro_cliente:
        condiciones.append("d.cliente_id = ?")
        params.append(filtro_cliente)
    if filtro_desde:
        condiciones.append("d.fecha_despacho >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        condiciones.append("d.fecha_despacho < ?")
        params.append(filtro_hasta + "T23:59:59" if "T" not in filtro_hasta else filtro_hasta)
    if filtro_estado:
        condiciones.append("d.estado = ?")
        params.append(filtro_estado)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT d.id, d.litros_despachados, d.fecha_despacho, d.estado,
               d.foto_ticket_url, d.odometro_km,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa,
               ch.nombre AS chofer_nombre,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               h.litros_autorizados,
               u_op.nombre AS operario_nombre
        FROM despachos d
        JOIN habilitaciones h ON h.id = d.habilitacion_id
        JOIN clientes cli ON cli.id = d.cliente_id
        JOIN vehiculos v ON v.id = d.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = d.gasolinera_id
        JOIN tarjetas t ON t.id = d.tarjeta_id
        JOIN usuarios u_op ON u_op.id = d.operario_id
        {where}
        ORDER BY d.id DESC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    cur.execute("SELECT id, nombre FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    conn.close()

    return render_template(
        "despachos/listado.html",
        lista=lista,
        gasolineras=gasolineras,
        clientes=clientes,
        filtro_gasolinera=filtro_gasolinera,
        filtro_cliente=filtro_cliente,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        filtro_estado=filtro_estado,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


# ── Detalle ───────────────────────────────────────────────────────────────────

@despachos_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.*,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa, v.tipo_combustible, v.marca, v.modelo,
               ch.nombre AS chofer_nombre, ch.ci AS chofer_ci,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial,
               h.litros_autorizados, h.fecha_habilitacion,
               u_op.nombre AS operario_nombre
        FROM despachos d
        JOIN habilitaciones h ON h.id = d.habilitacion_id
        JOIN clientes cli ON cli.id = d.cliente_id
        JOIN vehiculos v ON v.id = d.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = d.gasolinera_id
        JOIN tarjetas t ON t.id = d.tarjeta_id
        JOIN usuarios u_op ON u_op.id = d.operario_id
        WHERE d.id = ?
    """, (id,))
    despacho = cur.fetchone()
    conn.close()

    if not despacho:
        return redirect("/despachos")

    return render_template(
        "despachos/detalle.html",
        despacho=despacho,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


# ── Crear ─────────────────────────────────────────────────────────────────────

@despachos_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    _habs_cond = ""
    _habs_params = []
    if session.get("rol") == "operador_gasolinera":
        _habs_cond = "AND h.gasolinera_id = ?"
        _habs_params.append(session.get("gasolinera_id"))

    cur.execute(f"""
        SELECT h.id, h.litros_autorizados, h.tarjeta_id, h.subinventario_id,
               h.cliente_id, h.unidad_id, h.gasolinera_id,
               cli.nombre AS cliente_nombre,
               v.chapa AS unidad_chapa,
               ch.nombre AS chofer_nombre,
               g.nombre AS gasolinera_nombre,
               t.numero_parcial AS tarjeta_parcial
        FROM habilitaciones h
        JOIN clientes cli ON cli.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = h.gasolinera_id
        JOIN tarjetas t ON t.id = h.tarjeta_id
        WHERE h.estado = 'aprobada'
        AND NOT EXISTS (
            SELECT 1 FROM despachos d
            WHERE d.habilitacion_id = h.id AND d.estado = 'completado'
        )
        {_habs_cond}
        ORDER BY h.id DESC
    """, _habs_params)
    habilitaciones = cur.fetchall()
    conn.close()

    error = None
    hab_pre = request.args.get("habilitacion_id", "").strip()

    if request.method == "POST":
        habilitacion_id = request.form.get("habilitacion_id", "").strip()
        litros_str = request.form.get("litros_despachados", "0").strip()
        odometro_str = request.form.get("odometro_km", "").strip()
        observaciones = request.form.get("observaciones", "").strip()

        foto_ticket = request.files.get("foto_ticket")
        foto_vehiculo = request.files.get("foto_vehiculo")
        foto_odometro = request.files.get("foto_odometro")

        if not habilitacion_id:
            error = "Debe seleccionar una habilitación aprobada."
        elif not foto_ticket or not foto_ticket.filename:
            error = "La foto del ticket es obligatoria."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."
            if not error and litros <= 0:
                error = "Los litros despachados deben ser mayores a cero."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                SELECT h.*,
                       t.saldo_usable_l, t.estado AS tarjeta_estado,
                       s.litros_reservados AS sub_litros
                FROM habilitaciones h
                JOIN tarjetas t ON t.id = h.tarjeta_id
                LEFT JOIN subinventarios s ON s.id = h.subinventario_id
                WHERE h.id = ? AND h.estado = 'aprobada'
            """, (habilitacion_id,))
            hab = cur.fetchone()

            if not hab:
                error = "La habilitación no está disponible para despacho."
                conn.close()
            elif float(hab["saldo_usable_l"]) < litros - 0.001:
                error = (
                    f"Saldo insuficiente en la tarjeta. Disponible: "
                    f"{float(hab['saldo_usable_l']):,.2f} L, solicitado: {litros:,.2f} L."
                )
                conn.close()
            else:
                foto_ticket_url = _save_photo(foto_ticket, "tickets")
                if not foto_ticket_url:
                    error = "Formato de foto no válido. Use JPG, PNG o WEBP."
                    conn.close()

            if not error:
                foto_vehiculo_url = _save_photo(foto_vehiculo, "vehiculos")
                foto_odometro_url = _save_photo(foto_odometro, "odometros")

                try:
                    odometro_km = int(odometro_str) if odometro_str else None
                except ValueError:
                    odometro_km = None

                fecha_despacho = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                cur.execute("""
                    UPDATE tarjetas
                    SET saldo_usable_l = saldo_usable_l - ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (litros, hab["tarjeta_id"]))

                if hab["subinventario_id"] and hab["sub_litros"] is not None:
                    cur.execute("""
                        UPDATE subinventarios
                        SET litros_reservados = litros_reservados - ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (litros, hab["subinventario_id"]))

                cur.execute("""
                    UPDATE habilitaciones
                    SET litros_despachados = ?, estado = 'despachada',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (litros, habilitacion_id))

                cur.execute("""
                    INSERT INTO despachos
                        (habilitacion_id, gasolinera_id, tarjeta_id, cliente_id, unidad_id,
                         litros_despachados, foto_ticket_url, foto_vehiculo_url, foto_odometro_url,
                         odometro_km, observaciones, fecha_despacho, operario_id, estado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completado')
                """, (habilitacion_id, hab["gasolinera_id"], hab["tarjeta_id"],
                      hab["cliente_id"], hab["unidad_id"], litros,
                      foto_ticket_url, foto_vehiculo_url, foto_odometro_url,
                      odometro_km, observaciones or None, fecha_despacho,
                      session.get("user_id")))
                nuevo_id = cur.lastrowid

                cur.execute("""
                    INSERT INTO movimientos
                        (tipo, fecha, gasolinera_id, tarjeta_id, cliente_id, vehiculo_id,
                         litros, tipo_combustible, responsable_id, observaciones)
                    VALUES ('despacho', ?, ?, ?, ?, ?, ?, (
                        SELECT tipo_combustible FROM tarjetas WHERE id = ?
                    ), ?, ?)
                """, (fecha_despacho, hab["gasolinera_id"], hab["tarjeta_id"],
                      hab["cliente_id"], hab["unidad_id"], litros, hab["tarjeta_id"],
                      session.get("user_id"),
                      f"Despacho #{nuevo_id} — Habilitación #{habilitacion_id}"))

                conn.commit()
                conn.close()
                return redirect(f"/despachos/{nuevo_id}?ok=1")

    return render_template(
        "despachos/crear.html",
        error=error,
        habilitaciones=habilitaciones,
        hab_pre=hab_pre,
        hoy=date.today().isoformat(),
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        estado_labels=ESTADOS_HABILITACION_LABELS,
    )
