from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import REGIONES, TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM
from utils.auth import requiere_login

gasolineras_bp = Blueprint("gasolineras", __name__, url_prefix="/gasolineras")


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


def _combustibles_list(raw):
    """Devuelve lista de tipos válidos desde el campo combustible (puede ser CSV o valor único)."""
    if not raw:
        return []
    return [c.strip() for c in raw.split(",") if c.strip() in TIPOS_COMBUSTIBLE]


@gasolineras_bp.route("/")
def listado():
    redir = requiere_login()
    if redir:
        return redir

    buscar = request.args.get("buscar", "").strip()
    filtro_region = request.args.get("region", "").strip()
    filtro_estado = request.args.get("estado", "").strip()

    condiciones = []
    params = []

    if buscar:
        condiciones.append("(nombre LIKE ? OR gestor_responsable LIKE ? OR direccion LIKE ? OR provincia LIKE ?)")
        like = f"%{buscar}%"
        params.extend([like, like, like, like])
    if filtro_region:
        condiciones.append("region = ?")
        params.append(filtro_region)
    if filtro_estado:
        condiciones.append("estado = ?")
        params.append(filtro_estado)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT id, nombre, region, provincia, direccion, combustible, capacidad_l,
               gestor_responsable, estado, created_at
        FROM gasolineras
        {where}
        ORDER BY nombre ASC
    """, params)
    lista = cur.fetchall()
    conn.close()

    return render_template(
        "gasolineras/listado.html",
        lista=lista,
        buscar=buscar,
        filtro_region=filtro_region,
        filtro_estado=filtro_estado,
        regiones=REGIONES,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        combustibles_list=_combustibles_list,
    )


@gasolineras_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM gasolineras WHERE id = ?", (id,))
    gasolinera = cur.fetchone()

    if not gasolinera:
        conn.close()
        return redirect("/gasolineras")

    # Stock por tipo de combustible
    cur.execute("""
        SELECT tipo_combustible, COALESCE(SUM(litros), 0) AS stock
        FROM movimientos
        WHERE gasolinera_id = ? AND tipo = 'transferencia_entrada'
        GROUP BY tipo_combustible
        ORDER BY tipo_combustible
    """, (id,))
    stock_rows = cur.fetchall()
    stock_por_combustible = {r["tipo_combustible"]: float(r["stock"]) for r in stock_rows}
    stock_total = sum(stock_por_combustible.values())

    # Historial de transferencias recibidas
    cur.execute("""
        SELECT t.id, t.fecha_salida, t.fecha_llegada, t.tipo_combustible,
               t.litros_solicitados, t.litros_recibidos, t.pipa_chapa,
               t.chofer_pipa, t.estado,
               d.nombre AS deposito_nombre
        FROM transferencias t
        JOIN depositos d ON d.id = t.deposito_origen_id
        WHERE t.gasolinera_destino_id = ?
        ORDER BY t.fecha_salida DESC, t.id DESC
        LIMIT 50
    """, (id,))
    transferencias = cur.fetchall()
    conn.close()

    combustibles_gasolinera = _combustibles_list(gasolinera["combustible"])

    return render_template(
        "gasolineras/detalle.html",
        gasolinera=gasolinera,
        stock_total=stock_total,
        stock_por_combustible=stock_por_combustible,
        combustibles_gasolinera=combustibles_gasolinera,
        transferencias=transferencias,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


@gasolineras_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/gasolineras?access_error=Solo+Admin+y+PM+pueden+crear+gasolineras")

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        region = request.form.get("region", "").strip()
        provincia = request.form.get("provincia", "").strip()
        direccion = request.form.get("direccion", "").strip()
        combustibles_sel = request.form.getlist("combustibles")
        capacidad_str = request.form.get("capacidad_l", "0").strip()
        gestor = request.form.get("gestor_responsable", "").strip()
        estado = request.form.get("estado", "activo").strip()

        combustibles_validos = [c for c in combustibles_sel if c in TIPOS_COMBUSTIBLE]

        if not nombre:
            error = "El nombre es obligatorio."
        elif region not in REGIONES:
            error = "Región no válida."
        elif not combustibles_validos:
            error = "Debe seleccionar al menos un tipo de combustible."
        else:
            try:
                capacidad = float(capacidad_str)
            except ValueError:
                capacidad = 0.0
                error = "La capacidad debe ser un número."

        if not error:
            combustible_str = ",".join(combustibles_validos)
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gasolineras
                    (nombre, region, provincia, direccion, combustible, capacidad_l, gestor_responsable, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (nombre, region, provincia or None, direccion or None,
                  combustible_str, capacidad, gestor or None, estado))
            nuevo_id = cur.lastrowid
            conn.commit()
            conn.close()

            _registrar_auditoria(
                session.get("user_id"), "Creó gasolinera", "gasolineras", nuevo_id,
                valor_nuevo={"nombre": nombre, "region": region, "combustible": combustible_str}
            )
            return redirect("/gasolineras?ok=1")

    return render_template(
        "gasolineras/crear.html",
        error=error,
        regiones=REGIONES,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        combustibles_sel=[],
    )


@gasolineras_bp.route("/<int:id>/editar", methods=["GET", "POST"])
def editar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/gasolineras?access_error=Solo+Admin+y+PM+pueden+editar+gasolineras")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nombre, region, provincia, direccion, combustible,
               capacidad_l, gestor_responsable, estado
        FROM gasolineras WHERE id = ?
    """, (id,))
    gasolinera = cur.fetchone()

    if not gasolinera:
        conn.close()
        return redirect("/gasolineras")

    error = None
    combustibles_sel = _combustibles_list(gasolinera["combustible"])

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        region = request.form.get("region", "").strip()
        provincia = request.form.get("provincia", "").strip()
        direccion = request.form.get("direccion", "").strip()
        combustibles_form = request.form.getlist("combustibles")
        capacidad_str = request.form.get("capacidad_l", "0").strip()
        gestor = request.form.get("gestor_responsable", "").strip()
        estado = request.form.get("estado", "activo").strip()

        combustibles_validos = [c for c in combustibles_form if c in TIPOS_COMBUSTIBLE]

        if not nombre:
            error = "El nombre es obligatorio."
        elif region not in REGIONES:
            error = "Región no válida."
        elif not combustibles_validos:
            error = "Debe seleccionar al menos un tipo de combustible."
        else:
            try:
                capacidad = float(capacidad_str)
            except ValueError:
                capacidad = 0.0
                error = "La capacidad debe ser un número."

        if not error:
            combustible_str = ",".join(combustibles_validos)
            anterior = dict(gasolinera)
            cur.execute("""
                UPDATE gasolineras
                SET nombre = ?, region = ?, provincia = ?, direccion = ?,
                    combustible = ?, capacidad_l = ?, gestor_responsable = ?,
                    estado = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (nombre, region, provincia or None, direccion or None,
                  combustible_str, capacidad, gestor or None, estado, id))
            conn.commit()
            conn.close()

            _registrar_auditoria(
                session.get("user_id"), "Editó gasolinera", "gasolineras", id,
                valor_anterior=anterior,
                valor_nuevo={"nombre": nombre, "region": region,
                             "combustible": combustible_str, "estado": estado}
            )
            return redirect(f"/gasolineras/{id}?ok=1")

        combustibles_sel = combustibles_validos

    conn.close()

    return render_template(
        "gasolineras/editar.html",
        gasolinera=gasolinera,
        error=error,
        regiones=REGIONES,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        combustibles_sel=combustibles_sel,
    )


@gasolineras_bp.route("/<int:id>/toggle", methods=["POST"])
def toggle_estado(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/gasolineras?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT estado FROM gasolineras WHERE id = ?", (id,))
    row = cur.fetchone()
    if row:
        nuevo_estado = "inactivo" if row["estado"] == "activo" else "activo"
        cur.execute(
            "UPDATE gasolineras SET estado = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (nuevo_estado, id)
        )
        conn.commit()
        _registrar_auditoria(
            session.get("user_id"),
            f"Cambió estado a {nuevo_estado}", "gasolineras", id,
            valor_anterior={"estado": row["estado"]},
            valor_nuevo={"estado": nuevo_estado}
        )
    conn.close()
    return redirect("/gasolineras")
