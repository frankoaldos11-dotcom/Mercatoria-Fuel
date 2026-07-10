from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM
from utils.auth import requiere_login, requiere_staff
from utils.stock import stock_deposito

depositos_bp = Blueprint("depositos", __name__, url_prefix="/depositos")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


def _registrar_auditoria(usuario_id, accion, tabla, registro_id, valor_anterior=None, valor_nuevo=None):
    try:
        conn = conectar()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO auditoria
                (usuario_id, accion, tabla_afectada, registro_id, valor_anterior, valor_nuevo, ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id, accion, tabla, registro_id,
            str(valor_anterior) if valor_anterior else None,
            str(valor_nuevo) if valor_nuevo else None,
            request.remote_addr,
            request.headers.get("User-Agent", "")[:512],
        ))
        conn.commit()
        conn.close()
    except Exception:
        from flask import current_app
        current_app.logger.exception("Error registrando auditoría")




@depositos_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    buscar = request.args.get("buscar", "").strip()
    filtro_region = request.args.get("region", "").strip()
    filtro_combustible = request.args.get("combustible", "").strip()
    filtro_estado = request.args.get("estado", "").strip()

    condiciones = []
    params = []

    if buscar:
        condiciones.append("(d.nombre LIKE ? OR d.responsable LIKE ? OR d.direccion LIKE ?)")
        like = f"%{buscar}%"
        params.extend([like, like, like])
    if filtro_region:
        condiciones.append("d.region LIKE ?")
        params.append(f"%{filtro_region}%")
    if filtro_combustible:
        condiciones.append("d.tipo_combustible LIKE ?")
        params.append(f"%{filtro_combustible}%")
    if filtro_estado:
        condiciones.append("d.estado = ?")
        params.append(filtro_estado)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT d.id, d.nombre, d.region, d.tipo_combustible, d.capacidad_l,
               d.responsable, d.estado,
               COALESCE((
                   SELECT SUM(CASE WHEN m.tipo = 'transferencia_salida' THEN -m.litros ELSE m.litros END)
                   FROM movimientos m
                   WHERE m.deposito_id = d.id
                   AND m.tipo IN ('recepcion', 'transferencia_salida', 'transferencia_anulacion')
               ), 0) AS stock_actual
        FROM depositos d
        {where}
        ORDER BY d.nombre ASC
    """, params)
    lista = cur.fetchall()
    conn.close()

    return render_template(
        "depositos/listado.html",
        lista=lista,
        buscar=buscar,
        filtro_region=filtro_region,
        filtro_combustible=filtro_combustible,
        filtro_estado=filtro_estado,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@depositos_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM depositos WHERE id = ?", (id,))
    deposito = cur.fetchone()

    if not deposito:
        conn.close()
        return redirect("/depositos")

    stock_actual = stock_deposito(cur, id)

    # Historial de recepciones
    cur.execute("""
        SELECT r.id, r.fecha, r.proveedor, r.tipo_combustible,
               r.litros_factura, r.litros_recibidos, r.diferencia_l,
               r.no_vale, r.estado, u.nombre AS responsable_nombre
        FROM recepciones r
        JOIN usuarios u ON u.id = r.responsable_id
        WHERE r.deposito_id = ?
        ORDER BY r.fecha DESC, r.id DESC
        LIMIT 50
    """, (id,))
    recepciones = cur.fetchall()

    # Historial de transferencias salientes
    cur.execute("""
        SELECT t.id, t.fecha_salida, t.fecha_llegada, t.tipo_combustible,
               t.litros_solicitados, t.litros_recibidos, t.pipa_chapa,
               t.chofer_pipa, t.estado, g.nombre AS gasolinera_nombre
        FROM transferencias t
        JOIN gasolineras g ON g.id = t.gasolinera_destino_id
        WHERE t.deposito_origen_id = ?
        ORDER BY t.fecha_salida DESC, t.id DESC
        LIMIT 50
    """, (id,))
    transferencias = cur.fetchall()

    conn.close()

    return render_template(
        "depositos/detalle.html",
        deposito=deposito,
        stock_actual=stock_actual,
        recepciones=recepciones,
        transferencias=transferencias,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@depositos_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/depositos?access_error=Solo+Admin+y+PM+pueden+crear+depósitos")

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        region = request.form.get("region", "").strip()
        direccion = request.form.get("direccion", "").strip()
        tipos_sel = [t for t in request.form.getlist("tipo_combustible") if t in TIPOS_COMBUSTIBLE]
        tipo_combustible = ",".join(tipos_sel)
        capacidad_str = request.form.get("capacidad_l", "0").strip()
        responsable = request.form.get("responsable", "").strip()
        notas = request.form.get("notas", "").strip()
        estado = request.form.get("estado", "activo").strip()

        if not nombre:
            error = "El nombre es obligatorio."
        elif not region:
            error = "La provincia es obligatoria."
        elif not tipos_sel:
            error = "Selecciona al menos un tipo de combustible."
        else:
            try:
                capacidad = float(capacidad_str) if capacidad_str else None
            except ValueError:
                capacidad = None

            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO depositos
                    (nombre, region, direccion, tipo_combustible, capacidad_l, responsable, notas, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (nombre, region, direccion, tipo_combustible, capacidad, responsable, notas, estado))
            nuevo_id = cur.lastrowid
            conn.commit()
            conn.close()
            _registrar_auditoria(
                session.get("user_id"), "Creó depósito", "depositos", nuevo_id,
                valor_nuevo={"nombre": nombre, "region": region, "tipo_combustible": tipo_combustible}
            )
            return redirect("/depositos?ok=1")

    return render_template(
        "depositos/crear.html",
        error=error,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@depositos_bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/depositos?access_error=Solo+Admin+y+PM+pueden+editar+depósitos")

    conn = conectar()
    cur = conn.cursor()
    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        region = request.form.get("region", "").strip()
        direccion = request.form.get("direccion", "").strip()
        tipos_sel = [t for t in request.form.getlist("tipo_combustible") if t in TIPOS_COMBUSTIBLE]
        tipo_combustible = ",".join(tipos_sel)
        capacidad_str = request.form.get("capacidad_l", "0").strip()
        responsable = request.form.get("responsable", "").strip()
        notas = request.form.get("notas", "").strip()
        estado = request.form.get("estado", "activo").strip()

        if not nombre:
            error = "El nombre es obligatorio."
        elif not region:
            error = "La provincia es obligatoria."
        elif not tipos_sel:
            error = "Selecciona al menos un tipo de combustible."
        else:
            try:
                capacidad = float(capacidad_str) if capacidad_str else None
            except ValueError:
                capacidad = None

            cur.execute("SELECT * FROM depositos WHERE id = ?", (id,))
            anterior = dict(cur.fetchone() or {})
            cur.execute("""
                UPDATE depositos
                SET nombre = ?, region = ?, direccion = ?, tipo_combustible = ?,
                    capacidad_l = ?, responsable = ?, notas = ?, estado = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (nombre, region, direccion, tipo_combustible, capacidad, responsable, notas, estado, id))
            conn.commit()
            conn.close()
            _registrar_auditoria(
                session.get("user_id"), "Editó depósito", "depositos", id,
                valor_anterior=anterior,
                valor_nuevo={"nombre": nombre, "region": region, "tipo_combustible": tipo_combustible}
            )
            return redirect(f"/depositos/{id}?ok=1")

    cur.execute("SELECT * FROM depositos WHERE id = ?", (id,))
    deposito = cur.fetchone()
    conn.close()

    if not deposito:
        return redirect("/depositos")

    return render_template(
        "depositos/editar.html",
        deposito=deposito,
        error=error,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@depositos_bp.route("/<int:id>/toggle", methods=["POST"])
def toggle_estado(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/depositos?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM depositos WHERE id = ?", (id,))
    row = cur.fetchone()
    if row:
        nuevo_estado = "inactivo" if row["estado"] == "activo" else "activo"
        cur.execute(
            "UPDATE depositos SET estado = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (nuevo_estado, id)
        )
        conn.commit()
        _registrar_auditoria(
            session.get("user_id"),
            f"Cambió estado a {nuevo_estado}", "depositos", id,
            valor_anterior={"estado": row["estado"]},
            valor_nuevo={"estado": nuevo_estado}
        )
    conn.close()
    return redirect("/depositos")
