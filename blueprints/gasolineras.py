from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import (
    REGIONES, TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS, ROLES_ADMIN_PM,
    TIPOS_SUBINVENTARIO, TIPOS_SUBINVENTARIO_LABELS,
)
from utils.auth import requiere_login, requiere_staff
from utils.subinventarios import crear_subinventario, validar_tope_reserva, SubinventarioError

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
    redir = requiere_staff()
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

    # Stock por gasolinera/combustible: entradas - salidas (misma lógica que detalle)
    cur.execute("""
        SELECT gasolinera_id, tipo_combustible,
               COALESCE(SUM(CASE WHEN tipo = 'transferencia_entrada' THEN litros
                                  WHEN tipo = 'despacho' THEN -litros
                                  ELSE 0 END), 0) AS stock
        FROM movimientos
        WHERE tipo IN ('transferencia_entrada', 'despacho')
          AND tipo_combustible IS NOT NULL
        GROUP BY gasolinera_id, tipo_combustible
    """)
    _stock_rows = cur.fetchall()
    stock_gasolineras = {}
    for _r in _stock_rows:
        _gid = _r["gasolinera_id"]
        if _gid not in stock_gasolineras:
            stock_gasolineras[_gid] = {}
        stock_gasolineras[_gid][_r["tipo_combustible"]] = float(_r["stock"] or 0)

    # Capacidades de referencia por gasolinera/combustible
    cur.execute("SELECT gasolinera_id, tipo_combustible, capacidad_referencia_l FROM capacidades_gasolinera")
    capacidades_gasolineras = {}
    for _r in cur.fetchall():
        _gid = _r["gasolinera_id"]
        if _gid not in capacidades_gasolineras:
            capacidades_gasolineras[_gid] = {}
        capacidades_gasolineras[_gid][_r["tipo_combustible"]] = float(_r["capacidad_referencia_l"] or 0)

    # Saldo USD en tarjetas activas por gasolinera
    cur.execute("""
        SELECT gasolinera_id, COALESCE(SUM(saldo_usd), 0) AS saldo_usd_total
        FROM tarjetas WHERE estado = 'activa'
        GROUP BY gasolinera_id
    """)
    saldo_tarjetas_gas = {r["gasolinera_id"]: float(r["saldo_usd_total"] or 0) for r in cur.fetchall()}

    cur.execute("SELECT valor FROM configuracion WHERE clave = 'factor_litro_usd'")
    _frow = cur.fetchone()
    factor = float(_frow["valor"]) if _frow else 0.90

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
        stock_gasolineras=stock_gasolineras,
        capacidades_gasolineras=capacidades_gasolineras,
        saldo_tarjetas_gas=saldo_tarjetas_gas,
        factor=factor,
    )


@gasolineras_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_staff()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT * FROM gasolineras WHERE id = ?", (id,))
    gasolinera = cur.fetchone()

    if not gasolinera:
        conn.close()
        return redirect("/gasolineras")

    # Stock por tipo de combustible (entradas - salidas)
    cur.execute("""
        SELECT tipo_combustible,
               COALESCE(SUM(CASE WHEN tipo = 'transferencia_entrada' THEN litros
                                  WHEN tipo = 'despacho' THEN -litros
                                  ELSE 0 END), 0) AS stock
        FROM movimientos
        WHERE gasolinera_id = ?
          AND tipo IN ('transferencia_entrada', 'despacho')
          AND tipo_combustible IS NOT NULL
        GROUP BY tipo_combustible
        ORDER BY tipo_combustible
    """, (id,))
    stock_rows = cur.fetchall()
    stock_por_combustible = {r["tipo_combustible"]: float(r["stock"]) for r in stock_rows if r["tipo_combustible"]}

    # Capacidad de referencia por combustible (informativo, nunca bloquea)
    cur.execute("""
        SELECT tipo_combustible, capacidad_referencia_l
        FROM capacidades_gasolinera WHERE gasolinera_id = ?
    """, (id,))
    capacidad_por_combustible = {
        r["tipo_combustible"]: float(r["capacidad_referencia_l"] or 0) for r in cur.fetchall()
    }
    stock_total = float(sum(stock_por_combustible.values()))

    # Historial de transferencias recibidas
    cur.execute("""
        SELECT t.id, t.fecha_salida, t.fecha_llegada, t.tipo_combustible,
               t.litros_solicitados, t.litros_recibidos, t.litros_distribuidos, t.pipa_chapa,
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
    subinventarios_raw = cur.fetchall()

    # Despachos realizados
    cur.execute("""
        SELECT d.id, d.fecha_despacho, d.litros_despachados, d.estado,
               c.nombre AS cliente_nombre,
               v.chapa  AS unidad_chapa,
               t.numero_parcial AS tarjeta_parcial
        FROM despachos d
        JOIN clientes  c ON c.id = d.cliente_id
        JOIN vehiculos v ON v.id = d.unidad_id
        JOIN tarjetas  t ON t.id = d.tarjeta_id
        WHERE d.gasolinera_id = ?
        ORDER BY d.fecha_despacho DESC, d.id DESC
        LIMIT 20
    """, (id,))
    despachos_recientes = cur.fetchall()

    # Saldo USD en tarjetas activas de esta gasolinera
    cur.execute("""
        SELECT id, numero_parcial, tipo_combustible, saldo_usd, saldo_usable_l, estado
        FROM tarjetas WHERE gasolinera_id = ? AND estado = 'activa'
        ORDER BY numero_parcial ASC
    """, (id,))
    tarjetas_gas = cur.fetchall()
    saldo_usd_total_gas = sum(float(t["saldo_usd"] or 0) for t in tarjetas_gas)

    cur.execute("SELECT valor FROM configuracion WHERE clave = 'factor_litro_usd'")
    _frow = cur.fetchone()
    factor = float(_frow["valor"]) if _frow else 0.90

    conn.close()

    # suma_reservados computed from raw rows (accurate per-row activo flag)
    suma_reservados = sum(float(s["litros_reservados"]) for s in subinventarios_raw if s["activo"])
    disponible_venta = max(0.0, stock_total - suma_reservados)
    combustibles_gasolinera = _combustibles_list(gasolinera["combustible"])

    # Consolidate client subinventarios: one row per client with summed litros
    subinventarios_display = []
    _cliente_idx = {}
    for s in subinventarios_raw:
        cid = s["cliente_id"]
        if s["tipo"] == "cliente" and cid:
            if cid in _cliente_idx:
                idx = _cliente_idx[cid]
                subinventarios_display[idx] = dict(subinventarios_display[idx])
                subinventarios_display[idx]["litros_reservados"] = (
                    float(subinventarios_display[idx]["litros_reservados"]) +
                    float(s["litros_reservados"])
                )
            else:
                _cliente_idx[cid] = len(subinventarios_display)
                subinventarios_display.append(dict(s))
        else:
            subinventarios_display.append(dict(s))

    return render_template(
        "gasolineras/detalle.html",
        gasolinera=gasolinera,
        stock_total=stock_total,
        stock_por_combustible=stock_por_combustible,
        capacidad_por_combustible=capacidad_por_combustible,
        combustibles_gasolinera=combustibles_gasolinera,
        transferencias=transferencias,
        subinventarios=subinventarios_display,
        suma_reservados=suma_reservados,
        disponible_venta=disponible_venta,
        despachos_recientes=despachos_recientes,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        subinventario_labels=TIPOS_SUBINVENTARIO_LABELS,
        tarjetas_gas=tarjetas_gas,
        saldo_usd_total_gas=saldo_usd_total_gas,
        factor=factor,
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
        gestor = request.form.get("gestor_responsable", "").strip()
        estado = request.form.get("estado", "activo").strip()

        combustibles_validos = [c for c in combustibles_sel if c in TIPOS_COMBUSTIBLE]

        if not nombre:
            error = "El nombre es obligatorio."
        elif region not in REGIONES:
            error = "Región no válida."
        elif not combustibles_validos:
            error = "Debe seleccionar al menos un tipo de combustible."

        capacidades_por_tc = {}
        if not error:
            for tc in combustibles_validos:
                cap_str = request.form.get(f"capacidad_{tc}", "").strip()
                try:
                    capacidades_por_tc[tc] = float(cap_str) if cap_str else 0.0
                except ValueError:
                    capacidades_por_tc[tc] = 0.0

        if not error:
            combustible_str = ",".join(combustibles_validos)
            conn = conectar()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO gasolineras
                    (nombre, region, provincia, direccion, combustible, gestor_responsable, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nombre, region, provincia or None, direccion or None,
                  combustible_str, gestor or None, estado))
            nuevo_id = cur.lastrowid

            for tc, cap in capacidades_por_tc.items():
                cur.execute("""
                    INSERT INTO capacidades_gasolinera (gasolinera_id, tipo_combustible, capacidad_referencia_l)
                    VALUES (?, ?, ?)
                """, (nuevo_id, tc, cap))

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
               gestor_responsable, estado
        FROM gasolineras WHERE id = ?
    """, (id,))
    gasolinera = cur.fetchone()

    if not gasolinera:
        conn.close()
        return redirect("/gasolineras")

    cur.execute("""
        SELECT tipo_combustible, capacidad_referencia_l
        FROM capacidades_gasolinera WHERE gasolinera_id = ?
    """, (id,))
    capacidades_actuales = {r["tipo_combustible"]: float(r["capacidad_referencia_l"] or 0) for r in cur.fetchall()}

    error = None
    combustibles_sel = _combustibles_list(gasolinera["combustible"])

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        region = request.form.get("region", "").strip()
        provincia = request.form.get("provincia", "").strip()
        direccion = request.form.get("direccion", "").strip()
        combustibles_form = request.form.getlist("combustibles")
        gestor = request.form.get("gestor_responsable", "").strip()
        estado = request.form.get("estado", "activo").strip()

        combustibles_validos = [c for c in combustibles_form if c in TIPOS_COMBUSTIBLE]

        if not nombre:
            error = "El nombre es obligatorio."
        elif region not in REGIONES:
            error = "Región no válida."
        elif not combustibles_validos:
            error = "Debe seleccionar al menos un tipo de combustible."

        capacidades_por_tc = {}
        if not error:
            for tc in combustibles_validos:
                cap_str = request.form.get(f"capacidad_{tc}", "").strip()
                try:
                    capacidades_por_tc[tc] = float(cap_str) if cap_str else 0.0
                except ValueError:
                    capacidades_por_tc[tc] = 0.0

        if not error:
            combustible_str = ",".join(combustibles_validos)
            anterior = dict(gasolinera)
            cur.execute("""
                UPDATE gasolineras
                SET nombre = ?, region = ?, provincia = ?, direccion = ?,
                    combustible = ?, gestor_responsable = ?,
                    estado = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (nombre, region, provincia or None, direccion or None,
                  combustible_str, gestor or None, estado, id))

            # Limpiar capacidades de combustibles que se hayan desmarcado
            if combustibles_validos:
                placeholders = ",".join(["?"] * len(combustibles_validos))
                cur.execute(f"""
                    DELETE FROM capacidades_gasolinera
                    WHERE gasolinera_id = ? AND tipo_combustible NOT IN ({placeholders})
                """, (id, *combustibles_validos))
            else:
                cur.execute("DELETE FROM capacidades_gasolinera WHERE gasolinera_id = ?", (id,))

            # Upsert de capacidades para los combustibles seleccionados
            for tc, cap in capacidades_por_tc.items():
                cur.execute("""
                    INSERT INTO capacidades_gasolinera (gasolinera_id, tipo_combustible, capacidad_referencia_l)
                    VALUES (?, ?, ?)
                    ON CONFLICT (gasolinera_id, tipo_combustible)
                    DO UPDATE SET capacidad_referencia_l = excluded.capacidad_referencia_l,
                                  updated_at = CURRENT_TIMESTAMP
                """, (id, tc, cap))

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
        capacidades_actuales = capacidades_por_tc

    conn.close()

    return render_template(
        "gasolineras/editar.html",
        gasolinera=gasolinera,
        error=error,
        regiones=REGIONES,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        capacidades_actuales=capacidades_actuales,
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
                try:
                    crear_subinventario(cur, id, nombre, tipo, cliente_id, litros)
                except SubinventarioError as e:
                    error = str(e)
                    conn.close()
                else:
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
                try:
                    validar_tope_reserva(cur, id, litros, excluir_id=sub_id)
                except SubinventarioError as e:
                    error = str(e)
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
