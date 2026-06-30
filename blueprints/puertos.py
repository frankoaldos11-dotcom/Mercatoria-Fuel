from datetime import date

from flask import Blueprint, render_template, request, redirect, session

from database import conectar
from utils.auth import requiere_login
from utils.constants import (
    TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS,
    ESTADOS_LLEGADA_PUERTO, ESTADOS_LLEGADA_LABELS,
    ROLES_ADMIN_PM, ROLES_OPERARIO_DEP,
)

puertos_bp = Blueprint("puertos", __name__, url_prefix="/puertos")


def _requiere_dep():
    redir = requiere_login()
    if redir:
        return redir
    if session.get("rol") not in ROLES_OPERARIO_DEP + ["supervisor"]:
        return redirect("/dashboard")
    return None


# ── Listado ───────────────────────────────────────────────────────────────────

@puertos_bp.route("/")
def listado():
    redir = _requiere_dep()
    if redir:
        return redir

    filtro_puerto = request.args.get("puerto_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_fecha  = request.args.get("fecha", "").strip()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id, nombre FROM puertos WHERE activo = 1 ORDER BY nombre ASC")
    puertos = cur.fetchall()

    condiciones = []
    params = []

    if filtro_puerto:
        condiciones.append("lp.puerto_id = ?")
        params.append(filtro_puerto)
    if filtro_estado:
        condiciones.append("lp.estado = ?")
        params.append(filtro_estado)
    if filtro_fecha:
        condiciones.append("lp.fecha_llegada = ?")
        params.append(filtro_fecha)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    cur.execute(f"""
        SELECT lp.id, lp.numero_isotanque, lp.tipo_combustible, lp.litros,
               lp.fecha_llegada, lp.estado, lp.observaciones,
               p.nombre AS puerto_nombre,
               d.nombre AS deposito_nombre,
               u.nombre AS responsable_nombre
        FROM llegadas_puerto lp
        JOIN puertos p ON p.id = lp.puerto_id
        LEFT JOIN depositos d ON d.id = lp.deposito_destino_id
        JOIN usuarios u ON u.id = lp.responsable_id
        {where}
        ORDER BY lp.fecha_llegada DESC, lp.id DESC
    """, params)
    llegadas = cur.fetchall()
    conn.close()

    return render_template(
        "puertos/listado.html",
        llegadas=llegadas,
        puertos=puertos,
        filtro_puerto=filtro_puerto,
        filtro_estado=filtro_estado,
        filtro_fecha=filtro_fecha,
        estados=ESTADOS_LLEGADA_PUERTO,
        estado_labels=ESTADOS_LLEGADA_LABELS,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )


# ── Crear llegada ─────────────────────────────────────────────────────────────

@puertos_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = _requiere_dep()
    if redir:
        return redir
    if session.get("rol") not in ROLES_ADMIN_PM + ["operario_deposito"]:
        return redirect("/puertos/?access_error=Sin+permisos")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre FROM puertos WHERE activo = 1 ORDER BY nombre ASC")
    puertos = cur.fetchall()

    error = None

    if request.method == "POST":
        puerto_id      = request.form.get("puerto_id", "").strip()
        numero         = request.form.get("numero_isotanque", "").strip()
        tipo_comb      = request.form.get("tipo_combustible", "").strip()
        litros_str     = request.form.get("litros", "0").replace(",", ".")
        fecha_llegada  = request.form.get("fecha_llegada", date.today().isoformat()).strip()
        observaciones  = request.form.get("observaciones", "").strip()

        if not all([puerto_id, numero, tipo_comb]):
            error = "Puerto, número de isotanque y tipo de combustible son obligatorios."
        elif tipo_comb not in TIPOS_COMBUSTIBLE:
            error = "Tipo de combustible no válido."
        else:
            try:
                litros = float(litros_str)
            except ValueError:
                litros = 0.0
            if litros <= 0:
                error = "Los litros deben ser mayores a cero."

        if not error:
            cur.execute("""
                INSERT INTO llegadas_puerto
                    (puerto_id, numero_isotanque, tipo_combustible, litros,
                     fecha_llegada, estado, observaciones, responsable_id)
                VALUES (?, ?, ?, ?, ?, 'en_puerto', ?, ?)
            """, (puerto_id, numero, tipo_comb, litros,
                  fecha_llegada, observaciones or None, session.get("user_id")))
            conn.commit()
            conn.close()
            return redirect("/puertos/?ok=1")

    conn.close()
    return render_template(
        "puertos/crear.html",
        puertos=puertos,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        hoy=date.today().isoformat(),
        error=error,
    )


# ── Detalle ───────────────────────────────────────────────────────────────────

@puertos_bp.route("/<int:llegada_id>")
def detalle(llegada_id):
    redir = _requiere_dep()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT lp.*, p.nombre AS puerto_nombre,
               d.nombre AS deposito_nombre,
               u.nombre AS responsable_nombre
        FROM llegadas_puerto lp
        JOIN puertos p ON p.id = lp.puerto_id
        LEFT JOIN depositos d ON d.id = lp.deposito_destino_id
        JOIN usuarios u ON u.id = lp.responsable_id
        WHERE lp.id = ?
    """, (llegada_id,))
    llegada = cur.fetchone()

    if not llegada:
        conn.close()
        return redirect("/puertos/")

    tc = llegada["tipo_combustible"]
    cur.execute("""
        SELECT id, nombre, tipo_combustible, estado FROM depositos
        WHERE estado = 'activo' AND (
            tipo_combustible = ?
            OR tipo_combustible LIKE ?
            OR tipo_combustible LIKE ?
            OR tipo_combustible LIKE ?
        )
        ORDER BY nombre ASC
    """, (tc, tc + ',%', '%,' + tc, '%,' + tc + ',%'))
    depositos = cur.fetchall()
    conn.close()

    return render_template(
        "puertos/detalle.html",
        llegada=llegada,
        depositos=depositos,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
        estado_labels=ESTADOS_LLEGADA_LABELS,
        hoy=date.today().isoformat(),
        rol=session.get("rol"),
    )


# ── Confirmar transferencia a depósito ────────────────────────────────────────

@puertos_bp.route("/<int:llegada_id>/transferir", methods=["POST"])
def transferir(llegada_id):
    redir = requiere_login()
    if redir:
        return redirect("/login")
    if session.get("rol") not in ROLES_ADMIN_PM + ["operario_deposito"]:
        return redirect("/puertos/?access_error=Sin+permisos")

    deposito_id = request.form.get("deposito_destino_id", "").strip()
    fecha_transf = request.form.get("fecha_transferencia", date.today().isoformat()).strip()

    if not deposito_id:
        return redirect(f"/puertos/{llegada_id}?error=Selecciona+un+depósito")

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, litros, tipo_combustible, estado FROM llegadas_puerto WHERE id = ?
    """, (llegada_id,))
    llegada = cur.fetchone()

    if not llegada or llegada["estado"] != "en_puerto":
        conn.close()
        return redirect(f"/puertos/{llegada_id}?error=Estado+no+válido")

    cur.execute("""
        UPDATE llegadas_puerto
        SET deposito_destino_id = ?, fecha_transferencia = ?, estado = 'transferido',
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (deposito_id, fecha_transf, llegada_id))

    cur.execute("""
        INSERT INTO movimientos
            (tipo, fecha, deposito_id, litros, tipo_combustible, responsable_id, observaciones)
        VALUES ('recepcion', ?, ?, ?, ?, ?, ?)
    """, (fecha_transf, deposito_id, llegada["litros"], llegada["tipo_combustible"],
          session.get("user_id"),
          f"Llegada puerto #{llegada_id} — isotanque transferido a depósito"))

    conn.commit()
    conn.close()
    return redirect(f"/puertos/{llegada_id}?ok=1")


# ── Anular ────────────────────────────────────────────────────────────────────

@puertos_bp.route("/<int:llegada_id>/anular", methods=["POST"])
def anular(llegada_id):
    redir = requiere_login()
    if redir:
        return redirect("/login")
    if session.get("rol") != "admin":
        return redirect(f"/puertos/{llegada_id}?error=Solo+admin+puede+anular")

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        UPDATE llegadas_puerto SET estado = 'anulado', updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND estado = 'en_puerto'
    """, (llegada_id,))
    conn.commit()
    conn.close()
    return redirect("/puertos/?ok=1")
