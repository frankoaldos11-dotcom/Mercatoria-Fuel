from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import TIPOS_CLIENTE, TIPOS_CLIENTE_LABELS, ROLES_ADMIN_PM
from utils.auth import requiere_login, requiere_staff

clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")


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


@clientes_bp.route("/")
def listado():
    redir = requiere_staff()
    if redir:
        return redir

    buscar = request.args.get("buscar", "").strip()
    filtro_tipo = request.args.get("tipo", "").strip()
    filtro_estado = request.args.get("estado", "").strip()

    condiciones = []
    params = []

    if buscar:
        condiciones.append("(nombre LIKE ? OR codigo LIKE ? OR contacto_nombre LIKE ?)")
        like = f"%{buscar}%"
        params.extend([like, like, like])
    if filtro_tipo:
        condiciones.append("tipo = ?")
        params.append(filtro_tipo)
    if filtro_estado == "activo":
        condiciones.append("activo = 1")
    elif filtro_estado == "inactivo":
        condiciones.append("activo = 0")

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT id, nombre, codigo, tipo, contacto_nombre, contacto_telefono,
               contacto_email, subinventario_reservado_l, activo, created_at
        FROM clientes
        {where}
        ORDER BY nombre ASC
    """, params)
    lista = cur.fetchall()
    conn.close()

    return render_template(
        "clientes/listado.html",
        lista=lista,
        buscar=buscar,
        filtro_tipo=filtro_tipo,
        filtro_estado=filtro_estado,
        tipos_cliente=TIPOS_CLIENTE,
        tipos_cliente_labels=TIPOS_CLIENTE_LABELS,
    )


@clientes_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/clientes?access_error=Solo+Admin+y+PM+pueden+crear+clientes")

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        codigo = request.form.get("codigo", "").strip().upper()
        tipo = request.form.get("tipo", "").strip()
        contacto_nombre = request.form.get("contacto_nombre", "").strip()
        contacto_telefono = request.form.get("contacto_telefono", "").strip()
        contacto_email = request.form.get("contacto_email", "").strip().lower()
        subinventario_str = request.form.get("subinventario_reservado_l", "0").strip()
        notas = request.form.get("notas", "").strip()
        activo = 1 if request.form.get("activo") == "1" else 0

        if not nombre:
            error = "El nombre es obligatorio."
        elif not codigo:
            error = "El código es obligatorio."
        elif tipo not in TIPOS_CLIENTE:
            error = "Tipo de cliente no válido."
        else:
            try:
                reservado = float(subinventario_str)
            except ValueError:
                reservado = 0.0

            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT id FROM clientes WHERE codigo = ?", (codigo,))
            if cur.fetchone():
                error = f"Ya existe un cliente con el código {codigo}."
                conn.close()
            else:
                cur.execute("""
                    INSERT INTO clientes
                        (nombre, codigo, tipo, contacto_nombre, contacto_telefono,
                         contacto_email, subinventario_reservado_l, notas, activo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nombre, codigo, tipo, contacto_nombre, contacto_telefono,
                      contacto_email, reservado, notas, activo))
                nuevo_id = cur.lastrowid
                conn.commit()
                conn.close()
                _registrar_auditoria(
                    session.get("user_id"), "Creó cliente", "clientes", nuevo_id,
                    valor_nuevo={"nombre": nombre, "codigo": codigo, "tipo": tipo}
                )
                return redirect("/clientes?ok=1")

    return render_template(
        "clientes/crear.html",
        error=error,
        tipos_cliente=TIPOS_CLIENTE,
        tipos_cliente_labels=TIPOS_CLIENTE_LABELS,
    )


@clientes_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clientes WHERE id = ?", (id,))
    cliente = cur.fetchone()

    if not cliente:
        conn.close()
        return redirect("/clientes")

    cur.execute("""
        SELECT v.id, v.chapa, v.marca, v.modelo, v.anio, v.tipo_combustible,
               v.cuota_mensual_l, v.estado, v.color,
               ch.id AS chofer_id, ch.nombre AS chofer_nombre, ch.ci AS chofer_ci,
               ch.licencia_numero, ch.licencia_vencimiento, ch.telefono
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        WHERE v.cliente_id = ?
        ORDER BY v.chapa ASC
    """, (id,))
    unidades = cur.fetchall()

    conn.close()

    from datetime import date, timedelta
    hoy = date.today().isoformat()
    limite_30 = (date.today() + timedelta(days=30)).isoformat()

    from utils.constants import TIPOS_COMBUSTIBLE_LABELS
    return render_template(
        "clientes/detalle.html",
        cliente=cliente,
        unidades=unidades,
        tipos_cliente_labels=TIPOS_CLIENTE_LABELS,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=hoy,
        limite_30=limite_30,
    )


@clientes_bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/clientes/{id}?access_error=Solo+Admin+y+PM+pueden+editar+clientes")

    conn = conectar()
    cur = conn.cursor()
    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        codigo = request.form.get("codigo", "").strip().upper()
        tipo = request.form.get("tipo", "").strip()
        contacto_nombre = request.form.get("contacto_nombre", "").strip()
        contacto_telefono = request.form.get("contacto_telefono", "").strip()
        contacto_email = request.form.get("contacto_email", "").strip().lower()
        subinventario_str = request.form.get("subinventario_reservado_l", "0").strip()
        notas = request.form.get("notas", "").strip()
        activo = 1 if request.form.get("activo") == "1" else 0

        if not nombre:
            error = "El nombre es obligatorio."
        elif not codigo:
            error = "El código es obligatorio."
        elif tipo not in TIPOS_CLIENTE:
            error = "Tipo de cliente no válido."
        else:
            try:
                reservado = float(subinventario_str)
            except ValueError:
                reservado = 0.0

            cur.execute("SELECT id FROM clientes WHERE codigo = ? AND id != ?", (codigo, id))
            if cur.fetchone():
                error = f"Ya existe otro cliente con el código {codigo}."
            else:
                cur.execute("SELECT * FROM clientes WHERE id = ?", (id,))
                anterior = dict(cur.fetchone() or {})

                cur.execute("""
                    UPDATE clientes
                    SET nombre = ?, codigo = ?, tipo = ?, contacto_nombre = ?,
                        contacto_telefono = ?, contacto_email = ?,
                        subinventario_reservado_l = ?, notas = ?, activo = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (nombre, codigo, tipo, contacto_nombre, contacto_telefono,
                      contacto_email, reservado, notas, activo, id))
                conn.commit()
                conn.close()
                _registrar_auditoria(
                    session.get("user_id"), "Editó cliente", "clientes", id,
                    valor_anterior=anterior,
                    valor_nuevo={"nombre": nombre, "codigo": codigo, "tipo": tipo}
                )
                return redirect(f"/clientes/{id}?ok=1")

    cur.execute("SELECT * FROM clientes WHERE id = ?", (id,))
    cliente = cur.fetchone()
    conn.close()

    if not cliente:
        return redirect("/clientes")

    return render_template(
        "clientes/editar.html",
        cliente=cliente,
        error=error,
        tipos_cliente=TIPOS_CLIENTE,
        tipos_cliente_labels=TIPOS_CLIENTE_LABELS,
    )


@clientes_bp.route("/<int:id>/toggle", methods=["POST"])
def toggle_estado(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/clientes?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT activo FROM clientes WHERE id = ?", (id,))
    row = cur.fetchone()
    if row:
        nuevo_activo = 0 if row["activo"] else 1
        cur.execute(
            "UPDATE clientes SET activo = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (nuevo_activo, id)
        )
        conn.commit()
        _registrar_auditoria(
            session.get("user_id"),
            f"Cambió estado a {'activo' if nuevo_activo else 'inactivo'}",
            "clientes", id,
            valor_anterior={"activo": row["activo"]},
            valor_nuevo={"activo": nuevo_activo}
        )
    conn.close()
    return redirect("/clientes")
