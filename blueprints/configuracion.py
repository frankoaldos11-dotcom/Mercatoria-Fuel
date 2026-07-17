from flask import Blueprint, render_template, request, redirect, session, jsonify
from database import conectar, eliminar_columna_si_existe, columna_existe
from utils.auth import requiere_rol
from utils.constants import TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS

configuracion_bp = Blueprint("configuracion", __name__, url_prefix="/configuracion")

_ROLES_ADMIN = ["admin"]

_FLAG_RESETEO = "reseteo_inventario_habilitado"
_PALABRA_CONFIRMACION = "RESETEAR"

_FLAG_DROP_COLUMNAS = "drop_columnas_muertas_habilitado"
_PALABRA_CONFIRMACION_DROP = "ELIMINAR COLUMNAS"

# Columnas muertas a eliminar del esquema — confirmadas sin lectura ni escritura
# en el código de aplicación (ver diagnóstico previo). tarjetas.saldo_usd es la
# única con un riesgo real asociado (ver Barrera 4 en eliminar_columnas_muertas).
_COLUMNAS_A_ELIMINAR = [
    ("gasolineras", "capacidad_l"),
    ("clientes", "tipo"),
    ("tarjetas", "saldo_usd"),
]

# Orden de borrado: primero las tablas referenciadas por otras dentro de este mismo
# conjunto (despachos -> habilitaciones; movimientos_saldo_fincimex -> recepciones
# y llegadas_puerto), luego el resto sin dependencias cruzadas entre sí.
_TABLAS_TRANSACCIONALES = [
    "despachos",
    "movimientos_saldo_fincimex",
    "movimientos",
    "recepciones",
    "transferencias",
    "llegadas_puerto",
    "recargas_tarjetas",
    "devoluciones_tarjetas",
    "habilitaciones",
    "reservas_tienda",
    "conciliaciones",
    "movimientos_tl38",
]


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

_PARAMS_LABELS = {
    "compra_minima_litros": {
        "label": "Compra mínima por habilitación (litros)",
        "hint": "El mínimo de litros que debe tener una habilitación para ser aceptada.",
        "tipo": "numero",
    },
    "factor_litro_usd": {
        "label": "Factor de conversión litro→USD",
        "hint": "Multiplicador para convertir litros a USD al generar saldo Fincimex. Ejemplo: 0.90 = $0.90 por litro.",
        "tipo": "numero",
    },
}


@configuracion_bp.route("/", methods=["GET", "POST"])
def index():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    error = None
    ok = False

    if request.method == "POST":
        for clave in _PARAMS_LABELS:
            valor = request.form.get(clave, "").strip()
            if valor:
                cur.execute(
                    "UPDATE configuracion SET valor = ?, updated_at = CURRENT_TIMESTAMP WHERE clave = ?",
                    (valor, clave)
                )
        conn.commit()
        conn.close()
        return redirect("/configuracion/?ok=1")

    cur.execute("SELECT clave, valor FROM configuracion")
    rows = cur.fetchall()
    config = {r["clave"]: r["valor"] for r in rows}

    cur.execute("""
        SELECT pc.id, pc.gasolinera_id, pc.tipo_combustible,
               pc.precio_usd_por_litro, pc.activo,
               g.nombre AS gasolinera_nombre
        FROM precios_combustible pc
        JOIN gasolineras g ON g.id = pc.gasolinera_id
        ORDER BY g.nombre ASC, pc.tipo_combustible ASC
    """)
    precios = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado='activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()

    conn.close()

    reseteo_habilitado = config.get(_FLAG_RESETEO, "false") == "true"
    reseteo_resumen = session.pop("reseteo_resumen", None)
    drop_columnas_habilitado = config.get(_FLAG_DROP_COLUMNAS, "false") == "true"
    drop_columnas_resumen = session.pop("drop_columnas_resumen", None)

    return render_template(
        "configuracion/index.html",
        config=config,
        params_labels=_PARAMS_LABELS,
        precios=precios,
        gasolineras=gasolineras,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        tipos_combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        error=error,
        ok=ok,
        reseteo_habilitado=reseteo_habilitado,
        reseteo_resumen=reseteo_resumen,
        drop_columnas_habilitado=drop_columnas_habilitado,
        drop_columnas_resumen=drop_columnas_resumen,
    )


@configuracion_bp.route("/reseteo/toggle", methods=["POST"])
def reseteo_toggle():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracion WHERE clave = ?", (_FLAG_RESETEO,))
    row = cur.fetchone()
    actual = row["valor"] if row else "false"
    nuevo = "false" if actual == "true" else "true"

    cur.execute("""
        INSERT INTO configuracion (clave, valor)
        VALUES (?, ?)
        ON CONFLICT(clave)
        DO UPDATE SET valor = excluded.valor, updated_at = CURRENT_TIMESTAMP
    """, (_FLAG_RESETEO, nuevo))
    conn.commit()
    conn.close()

    _registrar_auditoria(
        session.get("user_id"),
        f"{'Activó' if nuevo == 'true' else 'Desactivó'} el modo de reseteo de inventario",
        "configuracion", 0,
        valor_anterior={_FLAG_RESETEO: actual},
        valor_nuevo={_FLAG_RESETEO: nuevo},
    )
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/resetear-inventario", methods=["POST"])
def resetear_inventario():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    # Barrera 2: releer el flag de la base de datos, nunca confiar en la UI.
    cur.execute("SELECT valor FROM configuracion WHERE clave = ?", (_FLAG_RESETEO,))
    row = cur.fetchone()
    if not row or row["valor"] != "true":
        conn.close()
        return redirect("/configuracion/?error=El+reseteo+de+inventario+no+está+habilitado")

    # Barrera 3: palabra de confirmación exacta.
    confirmacion = request.form.get("confirmacion", "").strip()
    if confirmacion != _PALABRA_CONFIRMACION:
        conn.close()
        return redirect("/configuracion/?error=Confirmación+incorrecta.+Debes+escribir+RESETEAR")

    # Conteos previos, para el resumen posterior.
    conteos = {}
    for tabla in _TABLAS_TRANSACCIONALES:
        cur.execute(f"SELECT COUNT(*) AS n FROM {tabla}")
        conteos[tabla] = cur.fetchone()["n"]

    cur.execute("SELECT COUNT(*) AS n FROM tarjetas")
    n_tarjetas = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM subinventarios")
    n_subinventarios = cur.fetchone()["n"]

    # Vaciado en el orden que respeta las FK internas del conjunto transaccional.
    for tabla in _TABLAS_TRANSACCIONALES:
        cur.execute(f"DELETE FROM {tabla}")

    # Saldos a 0 — se conservan las filas de configuración/maestros.
    cur.execute("""
        UPDATE tarjetas
        SET saldo_usable_l = 0, saldo_retenido_l = 0, updated_at = CURRENT_TIMESTAMP
    """)
    cur.execute("""
        UPDATE subinventarios
        SET litros_reservados = 0, updated_at = CURRENT_TIMESTAMP
    """)

    conn.commit()
    conn.close()

    resumen = {"tablas": conteos, "tarjetas_reseteadas": n_tarjetas, "subinventarios_reseteados": n_subinventarios}

    _registrar_auditoria(
        session.get("user_id"),
        "Reseteo de inventario a cero",
        "sistema", 0,
        valor_nuevo=resumen,
    )

    session["reseteo_resumen"] = resumen
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/limpieza-esquema/toggle", methods=["POST"])
def limpieza_esquema_toggle():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracion WHERE clave = ?", (_FLAG_DROP_COLUMNAS,))
    row = cur.fetchone()
    actual = row["valor"] if row else "false"
    nuevo = "false" if actual == "true" else "true"

    cur.execute("""
        INSERT INTO configuracion (clave, valor)
        VALUES (?, ?)
        ON CONFLICT(clave)
        DO UPDATE SET valor = excluded.valor, updated_at = CURRENT_TIMESTAMP
    """, (_FLAG_DROP_COLUMNAS, nuevo))
    conn.commit()
    conn.close()

    _registrar_auditoria(
        session.get("user_id"),
        f"{'Activó' if nuevo == 'true' else 'Desactivó'} el modo de limpieza de esquema",
        "configuracion", 0,
        valor_anterior={_FLAG_DROP_COLUMNAS: actual},
        valor_nuevo={_FLAG_DROP_COLUMNAS: nuevo},
    )
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/eliminar-columnas-muertas", methods=["POST"])
def eliminar_columnas_muertas():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    # Barrera 2: releer el flag de la base de datos, nunca confiar en la UI.
    cur.execute("SELECT valor FROM configuracion WHERE clave = ?", (_FLAG_DROP_COLUMNAS,))
    row = cur.fetchone()
    if not row or row["valor"] != "true":
        conn.close()
        return redirect("/configuracion/?error=La+limpieza+de+esquema+no+está+habilitada")

    # Barrera 3: palabra de confirmación exacta.
    confirmacion = request.form.get("confirmacion", "").strip()
    if confirmacion != _PALABRA_CONFIRMACION_DROP:
        conn.close()
        return redirect(
            "/configuracion/?error=Confirmación+incorrecta.+Debes+escribir+ELIMINAR+COLUMNAS"
        )

    # Barrera 4: no dejar tarjetas con saldo real sin recuperar. Si alguna
    # tarjeta tiene saldo_usable_l = 0 pero saldo_usd > 0, ese saldo depende
    # todavía de la columna que estamos por borrar — se aborta todo el
    # botón (ninguna de las 3 columnas se toca), no solo la de tarjetas.
    # Se saltea sola si saldo_usd ya no existe (ejecución idempotente: si ya
    # se corrió el DROP antes, no hay columna que consultar ni riesgo posible).
    tarjetas_en_riesgo = 0
    if columna_existe(cur, "tarjetas", "saldo_usd"):
        cur.execute("""
            SELECT COUNT(*) AS n FROM tarjetas WHERE saldo_usable_l = 0 AND saldo_usd > 0
        """)
        tarjetas_en_riesgo = cur.fetchone()["n"]
    if tarjetas_en_riesgo > 0:
        conn.close()
        return redirect(
            f"/configuracion/?error={tarjetas_en_riesgo}+tarjeta(s)+tienen+saldo_usd+"
            "sin+reflejar+en+saldo_usable_l+—+resetea+el+inventario+o+corrígelas+antes+de+continuar"
        )

    for tabla, columna in _COLUMNAS_A_ELIMINAR:
        eliminar_columna_si_existe(cur, tabla, columna)

    conn.commit()
    conn.close()

    resumen = {"columnas": [f"{t}.{c}" for t, c in _COLUMNAS_A_ELIMINAR]}

    _registrar_auditoria(
        session.get("user_id"),
        "Eliminación de columnas muertas del esquema",
        "sistema", 0,
        valor_nuevo=resumen,
    )

    session["drop_columnas_resumen"] = resumen
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/guardar", methods=["POST"])
def precios_guardar():
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    gid = request.form.get("gasolinera_id", "").strip()
    tc = request.form.get("tipo_combustible", "").strip()
    precio_str = request.form.get("precio_usd_por_litro", "0").strip()

    try:
        precio = float(precio_str.replace(",", "."))
    except ValueError:
        precio = 0.0

    if not gid or not tc or precio <= 0:
        return redirect("/configuracion/?error=Datos+inválidos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO precios_combustible (gasolinera_id, tipo_combustible, precio_usd_por_litro, activo)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(gasolinera_id, tipo_combustible)
        DO UPDATE SET precio_usd_por_litro=excluded.precio_usd_por_litro,
                      activo=1, updated_at=CURRENT_TIMESTAMP
    """, (gid, tc, precio))
    conn.commit()
    conn.close()
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/<int:pid>/toggle", methods=["POST"])
def precios_toggle(pid):
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT activo FROM precios_combustible WHERE id=?", (pid,))
    row = cur.fetchone()
    if row:
        cur.execute("""
            UPDATE precios_combustible SET activo=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (0 if row["activo"] else 1, pid))
        conn.commit()
    conn.close()
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/<int:pid>/eliminar", methods=["POST"])
def precios_eliminar(pid):
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("DELETE FROM precios_combustible WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    return redirect("/configuracion/?ok=1")


@configuracion_bp.route("/precios/<int:pid>/editar", methods=["POST"])
def precios_editar(pid):
    redir = requiere_rol(*_ROLES_ADMIN)
    if redir:
        return jsonify({"error": "Sin permiso"}), 403

    precio_str = request.form.get("precio_usd_por_litro", "0").strip()
    try:
        precio = float(precio_str.replace(",", "."))
    except ValueError:
        precio = 0.0

    if precio <= 0:
        return jsonify({"error": "Precio inválido"}), 400

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE precios_combustible SET precio_usd_por_litro=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
    """, (precio, pid))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "precio": f"{precio:.4f}"})
