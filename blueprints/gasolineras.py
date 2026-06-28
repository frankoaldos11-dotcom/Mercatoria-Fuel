from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import REGIONES, TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM
from utils.auth import requiere_login

gasolineras_bp = Blueprint("gasolineras", __name__, url_prefix="/gasolineras")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


def _registrar_auditoria(usuario_id, accion, tabla, registro_id, valor_anterior=None, valor_nuevo=None):
    try:
        from flask import request as req
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
            req.remote_addr,
            req.headers.get("User-Agent", "")[:512],
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        import traceback; traceback.print_exc()


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
        condiciones.append("(nombre LIKE ? OR gestor_responsable LIKE ? OR direccion LIKE ?)")
        like = f"%{buscar}%"
        params.extend([like, like, like])
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
        SELECT id, nombre, region, direccion, combustible, capacidad_l,
               gestor_responsable, estado, created_at
        FROM gasolineras
        {where}
        ORDER BY id DESC
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
        direccion = request.form.get("direccion", "").strip()
        combustible = request.form.get("combustible", "").strip()
        capacidad_str = request.form.get("capacidad_l", "0").strip()
        gestor = request.form.get("gestor_responsable", "").strip()
        estado = request.form.get("estado", "activo").strip()

        if not nombre:
            error = "El nombre es obligatorio."
        elif region not in REGIONES:
            error = "Región no válida."
        elif combustible not in TIPOS_COMBUSTIBLE:
            error = "Tipo de combustible no válido."
        else:
            try:
                capacidad = float(capacidad_str)
            except ValueError:
                capacidad = 0.0
                error = "La capacidad debe ser un número."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gasolineras
                    (nombre, region, direccion, combustible, capacidad_l, gestor_responsable, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nombre, region, direccion, combustible, capacidad, gestor, estado))
            nuevo_id = cur.lastrowid
            conn.commit()
            conn.close()

            _registrar_auditoria(
                session.get("user_id"), "Creó gasolinera", "gasolineras", nuevo_id,
                valor_nuevo={"nombre": nombre, "region": region, "combustible": combustible}
            )
            return redirect("/gasolineras?ok=1")

    return render_template(
        "gasolineras/crear.html",
        error=error,
        regiones=REGIONES,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
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

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        region = request.form.get("region", "").strip()
        direccion = request.form.get("direccion", "").strip()
        combustible = request.form.get("combustible", "").strip()
        capacidad_str = request.form.get("capacidad_l", "0").strip()
        gestor = request.form.get("gestor_responsable", "").strip()
        estado = request.form.get("estado", "activo").strip()

        if not nombre:
            error = "El nombre es obligatorio."
        elif region not in REGIONES:
            error = "Región no válida."
        elif combustible not in TIPOS_COMBUSTIBLE:
            error = "Tipo de combustible no válido."
        else:
            try:
                capacidad = float(capacidad_str)
            except ValueError:
                capacidad = 0.0
                error = "La capacidad debe ser un número."

        if not error:
            # Capturar valor anterior para auditoría
            cur.execute("SELECT * FROM gasolineras WHERE id = ?", (id,))
            anterior = dict(cur.fetchone() or {})

            cur.execute("""
                UPDATE gasolineras
                SET nombre = ?, region = ?, direccion = ?, combustible = ?,
                    capacidad_l = ?, gestor_responsable = ?, estado = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """, (nombre, region, direccion, combustible, capacidad, gestor, estado, id))
            conn.commit()
            conn.close()

            _registrar_auditoria(
                session.get("user_id"), "Editó gasolinera", "gasolineras", id,
                valor_anterior=anterior,
                valor_nuevo={"nombre": nombre, "region": region, "combustible": combustible, "estado": estado}
            )
            return redirect("/gasolineras")

    cur.execute("""
        SELECT id, nombre, region, direccion, combustible, capacidad_l,
               gestor_responsable, estado
        FROM gasolineras WHERE id = ?
    """, (id,))
    gasolinera = cur.fetchone()
    conn.close()

    if not gasolinera:
        return redirect("/gasolineras")

    return render_template(
        "gasolineras/editar.html",
        gasolinera=gasolinera,
        error=error,
        regiones=REGIONES,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
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
            "UPDATE gasolineras SET estado = ?, updated_at = datetime('now') WHERE id = ?",
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
