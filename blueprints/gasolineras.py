from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import (
    REGIONES, TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM,
    TIPOS_SUBINVENTARIO, TIPOS_SUBINVENTARIO_LABELS,
)
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


def _stock_gasolinera(cur, gasolinera_id):
    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS stock
        FROM movimientos
        WHERE gasolinera_id = ? AND tipo = 'transferencia_entrada'
    """, (gasolinera_id,))
    return float(cur.fetchone()["stock"] or 0)


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
    stock_por_combustible = {r["tipo_combustible"]: float(r["stock"]) for r in stock_rows if r["tipo_combustible"]}
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

    # Subinventarios
    cur.execute("""
        SELECT s.id, s.nombre, s.tipo, s.orden_prioridad, s.litros_reservados,
               s.activo, s.cliente_id, c.nombre AS cliente_nombre
        FROM subinventarios s
        LEFT JOIN clientes c ON c.id = s.cliente_id
        WHERE s.gasolinera_id = ?
        ORDER BY s.orden_prioridad ASC, s.id ASC
    """, (id,))
    subinventarios = cur.fetchall()
    conn.close()

    suma_reservados = sum(float(s["litros_reservados"]) for s in subinventarios if s["activo"])
    disponible_venta = max(0.0, stock_total - suma_reservados)
    combustibles_gasolinera = _combustibles_list(gasolinera["combustible"])

    return render_template(
        "gasolineras/detalle.html",
        gasolinera=gasolinera,
        stock_total=stock_total,
        stock_por_combustible=stock_por_combustible,
        combustibles_gasolinera=combustibles_gasolinera,
        transferencias=transferencias,
        subinventarios=subinventarios,
        suma_reservados=suma_reservados,
        disponible_venta=disponible_venta,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        subinventario_labels=TIPOS_SUBINVENTARIO_LABELS,
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


# ── Subinventarios: crear ─────────────────────────────────────────────────────

@gasolineras_bp.route("/<int:id>/subinventarios/crear", methods=["GET", "POST"])
def subinventario_crear(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/gasolineras/{id}?access_error=Solo+Admin+y+PM+pueden+gestionar+subinventarios")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM gasolineras WHERE id = ?", (id,))
    gasolinera = cur.fetchone()
    if not gasolinera:
        conn.close()
        return redirect("/gasolineras")

    cur.execute("SELECT id, nombre FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        tipo = request.form.get("tipo", "").strip()
        litros_str = request.form.get("litros_reservados", "0").strip()
        cliente_id = request.form.get("cliente_id", "").strip() or None

        if not nombre:
            error = "El nombre es obligatorio."
        elif tipo not in TIPOS_SUBINVENTARIO:
            error = "Tipo no válido."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."

            if not error and litros < 0:
                error = "Los litros reservados no pueden ser negativos."

            if not error:
                conn = conectar()
                cur = conn.cursor()
                stock_actual = _stock_gasolinera(cur, id)
                cur.execute("""
                    SELECT COALESCE(SUM(litros_reservados), 0) AS total
                    FROM subinventarios WHERE gasolinera_id = ? AND activo = 1
                """, (id,))
                suma_actual = float(cur.fetchone()["total"] or 0)

                if suma_actual + litros > stock_actual + 0.001:
                    error = (
                        f"La reserva total ({suma_actual + litros:,.2f} L) superaría el stock "
                        f"físico actual ({stock_actual:,.2f} L)."
                    )
                    conn.close()
                else:
                    cur.execute("""
                        SELECT COALESCE(MAX(orden_prioridad), -1) + 1 AS siguiente
                        FROM subinventarios WHERE gasolinera_id = ? AND activo = 1
                    """, (id,))
                    orden = cur.fetchone()["siguiente"]
                    cur.execute("""
                        INSERT INTO subinventarios
                            (gasolinera_id, nombre, tipo, orden_prioridad, litros_reservados, cliente_id, activo)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """, (id, nombre, tipo, orden, litros, cliente_id or None))
                    conn.commit()
                    conn.close()
                    return redirect(f"/gasolineras/{id}?ok=1")

    return render_template(
        "gasolineras/subinventario_crear.html",
        gasolinera=gasolinera,
        error=error,
        clientes=clientes,
        tipos_subinventario=TIPOS_SUBINVENTARIO,
        subinventario_labels=TIPOS_SUBINVENTARIO_LABELS,
    )


# ── Subinventarios: editar ────────────────────────────────────────────────────

@gasolineras_bp.route("/<int:id>/subinventarios/<int:sub_id>/editar", methods=["GET", "POST"])
def subinventario_editar(id, sub_id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/gasolineras/{id}?access_error=Solo+Admin+y+PM+pueden+gestionar+subinventarios")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM gasolineras WHERE id = ?", (id,))
    gasolinera = cur.fetchone()
    cur.execute("SELECT * FROM subinventarios WHERE id = ? AND gasolinera_id = ?", (sub_id, id))
    sub = cur.fetchone()
    if not gasolinera or not sub:
        conn.close()
        return redirect(f"/gasolineras/{id}")

    cur.execute("SELECT id, nombre FROM clientes WHERE activo = 1 ORDER BY nombre ASC")
    clientes = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        tipo = request.form.get("tipo", "").strip()
        litros_str = request.form.get("litros_reservados", "0").strip()
        cliente_id = request.form.get("cliente_id", "").strip() or None

        if not nombre:
            error = "El nombre es obligatorio."
        elif tipo not in TIPOS_SUBINVENTARIO:
            error = "Tipo no válido."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."

            if not error and litros < 0:
                error = "Los litros reservados no pueden ser negativos."

            if not error:
                conn = conectar()
                cur = conn.cursor()
                stock_actual = _stock_gasolinera(cur, id)
                cur.execute("""
                    SELECT COALESCE(SUM(litros_reservados), 0) AS total
                    FROM subinventarios WHERE gasolinera_id = ? AND activo = 1 AND id != ?
                """, (id, sub_id))
                suma_otros = float(cur.fetchone()["total"] or 0)

                if suma_otros + litros > stock_actual + 0.001:
                    error = (
                        f"La reserva total ({suma_otros + litros:,.2f} L) superaría el stock "
                        f"físico actual ({stock_actual:,.2f} L)."
                    )
                    conn.close()
                else:
                    litros_anterior = float(sub["litros_reservados"])
                    cur.execute("""
                        UPDATE subinventarios
                        SET nombre = ?, tipo = ?,
                            litros_reservados = ?, cliente_id = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (nombre, tipo, litros, cliente_id or None, sub_id))

                    if abs(litros - litros_anterior) > 0.001:
                        delta = litros - litros_anterior
                        cur.execute("""
                            INSERT INTO movimientos
                                (tipo, fecha, gasolinera_id,
                                 subinventario_origen_id, subinventario_destino_id,
                                 litros, responsable_id, observaciones)
                            VALUES ('reasignacion', date('now'), ?, ?, ?, ?, ?, ?)
                        """, (
                            id,
                            sub_id if delta < 0 else None,
                            sub_id if delta > 0 else None,
                            abs(delta),
                            session.get("user_id"),
                            f"Ajuste directo reserva subinventario #{sub_id} — {nombre}",
                        ))

                    conn.commit()
                    conn.close()
                    return redirect(f"/gasolineras/{id}?ok=1")

    return render_template(
        "gasolineras/subinventario_editar.html",
        gasolinera=gasolinera,
        sub=sub,
        error=error,
        clientes=clientes,
        tipos_subinventario=TIPOS_SUBINVENTARIO,
        subinventario_labels=TIPOS_SUBINVENTARIO_LABELS,
    )


# ── Subinventarios: toggle ────────────────────────────────────────────────────

@gasolineras_bp.route("/<int:id>/subinventarios/<int:sub_id>/toggle", methods=["POST"])
def subinventario_toggle(id, sub_id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/gasolineras/{id}?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT activo FROM subinventarios WHERE id = ? AND gasolinera_id = ?", (sub_id, id))
    row = cur.fetchone()
    if row:
        nuevo = 0 if row["activo"] else 1
        cur.execute(
            "UPDATE subinventarios SET activo = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (nuevo, sub_id)
        )
        conn.commit()
    conn.close()
    return redirect(f"/gasolineras/{id}?ok=1")


# ── Subinventarios: mover (↑↓) ───────────────────────────────────────────────

@gasolineras_bp.route("/<int:id>/subinventarios/<int:sub_id>/mover", methods=["POST"])
def subinventario_mover(id, sub_id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/gasolineras/{id}?access_error=Sin+permisos")

    direction = request.form.get("dir", "down")

    conn = conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, orden_prioridad FROM subinventarios WHERE id = ? AND gasolinera_id = ? AND activo = 1",
        (sub_id, id),
    )
    actual = cur.fetchone()
    if not actual:
        conn.close()
        return redirect(f"/gasolineras/{id}")

    cur.execute("""
        SELECT id, orden_prioridad FROM subinventarios
        WHERE gasolinera_id = ? AND activo = 1 AND orden_prioridad {} ?
        ORDER BY orden_prioridad {} LIMIT 1
    """.format("<" if direction == "up" else ">",
               "DESC" if direction == "up" else "ASC"),
        (id, actual["orden_prioridad"]),
    )
    vecino = cur.fetchone()

    if vecino:
        cur.execute(
            "UPDATE subinventarios SET orden_prioridad = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (vecino["orden_prioridad"], sub_id),
        )
        cur.execute(
            "UPDATE subinventarios SET orden_prioridad = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (actual["orden_prioridad"], vecino["id"]),
        )
        conn.commit()
    conn.close()
    return redirect(f"/gasolineras/{id}?ok=1")


# ── Reasignación de reservas ──────────────────────────────────────────────────

@gasolineras_bp.route("/<int:id>/reasignar", methods=["GET", "POST"])
def reasignar(id):
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect(f"/gasolineras/{id}?access_error=Solo+Admin+y+PM+pueden+reasignar+reservas")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM gasolineras WHERE id = ?", (id,))
    gasolinera = cur.fetchone()
    if not gasolinera:
        conn.close()
        return redirect("/gasolineras")

    cur.execute("""
        SELECT id, nombre, tipo, litros_reservados
        FROM subinventarios WHERE gasolinera_id = ? AND activo = 1
        ORDER BY orden_prioridad ASC, id ASC
    """, (id,))
    subinventarios = cur.fetchall()
    conn.close()

    error = None

    if request.method == "POST":
        origen_id_str = request.form.get("origen_id", "").strip()
        destino_id_str = request.form.get("destino_id", "").strip()
        litros_str = request.form.get("litros", "0").strip()

        if not origen_id_str or not destino_id_str:
            error = "Debe seleccionar subinventario origen y destino."
        elif origen_id_str == destino_id_str:
            error = "El origen y el destino no pueden ser el mismo subinventario."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
                error = "Los litros deben ser un número válido."

            if not error and litros <= 0:
                error = "Los litros a reasignar deben ser mayores a cero."

        if not error:
            conn = conectar()
            cur = conn.cursor()
            cur.execute("SELECT litros_reservados FROM subinventarios WHERE id = ? AND gasolinera_id = ? AND activo = 1",
                        (origen_id_str, id))
            origen_row = cur.fetchone()
            if not origen_row:
                error = "Subinventario origen no encontrado o inactivo."
                conn.close()
            elif float(origen_row["litros_reservados"]) < litros - 0.001:
                error = (
                    f"El subinventario origen solo tiene {float(origen_row['litros_reservados']):,.2f} L "
                    f"reservados y no puede ceder {litros:,.2f} L."
                )
                conn.close()
            else:
                cur.execute(
                    "UPDATE subinventarios SET litros_reservados = litros_reservados - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (litros, origen_id_str)
                )
                cur.execute(
                    "UPDATE subinventarios SET litros_reservados = litros_reservados + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (litros, destino_id_str)
                )
                cur.execute("""
                    INSERT INTO movimientos
                        (tipo, fecha, gasolinera_id,
                         subinventario_origen_id, subinventario_destino_id,
                         litros, responsable_id, observaciones)
                    VALUES ('reasignacion', date('now'), ?, ?, ?, ?, ?, ?)
                """, (id, origen_id_str, destino_id_str, litros, session.get("user_id"),
                      "Reasignación de reserva entre subinventarios"))
                conn.commit()
                conn.close()
                return redirect(f"/gasolineras/{id}?ok=1")

    return render_template(
        "gasolineras/reasignar.html",
        gasolinera=gasolinera,
        subinventarios=subinventarios,
        error=error,
        subinventario_labels=TIPOS_SUBINVENTARIO_LABELS,
    )
