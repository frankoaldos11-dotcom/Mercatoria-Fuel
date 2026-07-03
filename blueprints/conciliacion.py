from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, session
from database import conectar
from utils.constants import (
    ESTADOS_CONCILIACION, TURNOS_CONCILIACION, TURNOS_CONCILIACION_LABELS,
    TIPOS_COMBUSTIBLE_LABELS,
)
from utils.auth import requiere_login

conciliacion_bp = Blueprint("conciliacion", __name__, url_prefix="/conciliacion")

_DIFF_TOLERANCIA = 0.005  # 0.5%


def _detalle_habilitaciones(cur, gasolinera_id, fecha):
    """Devuelve habilitaciones del día para la vista de cierre de turno."""
    manana = (date.fromisoformat(fecha) + timedelta(days=1)).isoformat()
    cur.execute("""
        SELECT h.id, h.estado,
               h.litros_autorizados, h.litros_despachados,
               v.tipo_combustible,
               c.nombre AS cliente_nombre,
               v.chapa  AS unidad_chapa
        FROM habilitaciones h
        JOIN clientes c  ON c.id = h.cliente_id
        JOIN vehiculos v ON v.id = h.unidad_id
        WHERE h.gasolinera_id = ?
          AND h.fecha_habilitacion >= ?
          AND h.fecha_habilitacion <  ?
        ORDER BY h.id ASC
    """, (gasolinera_id, fecha, manana))
    return cur.fetchall()


def _calcular_totales(cur, gasolinera_id, fecha):
    """Suma entradas y despachos de esa gasolinera en esa fecha."""
    manana = (date.fromisoformat(fecha) + timedelta(days=1)).isoformat()

    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS total
        FROM movimientos
        WHERE gasolinera_id = ? AND tipo = 'transferencia_entrada'
        AND fecha >= ? AND fecha < ?
    """, (gasolinera_id, fecha, manana))
    total_entrada = float(cur.fetchone()["total"] or 0)

    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS total
        FROM movimientos
        WHERE gasolinera_id = ? AND tipo = 'despacho'
        AND fecha >= ? AND fecha < ?
    """, (gasolinera_id, fecha, manana))
    total_despachado = float(cur.fetchone()["total"] or 0)

    return total_entrada, total_despachado


# ── Listado ───────────────────────────────────────────────────────────────────

@conciliacion_bp.route("/")
def listado():
    redir = requiere_login()
    if redir:
        return redir

    filtro_gasolinera = request.args.get("gasolinera_id", "").strip()
    filtro_estado = request.args.get("estado", "").strip()
    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()

    condiciones = []
    params = []

    if filtro_gasolinera:
        condiciones.append("c.gasolinera_id = ?")
        params.append(filtro_gasolinera)
    if filtro_estado:
        condiciones.append("c.estado = ?")
        params.append(filtro_estado)
    if filtro_desde:
        condiciones.append("c.fecha >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        condiciones.append("c.fecha <= ?")
        params.append(filtro_hasta)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT c.id, c.fecha, c.turno, c.estado,
               c.saldo_fisico_inicio_l, c.saldo_fisico_fin_l,
               c.total_entrada_l, c.total_despachado_l,
               c.diferencia_l, c.diferencia_porcentaje,
               g.nombre AS gasolinera_nombre,
               u.nombre AS responsable_nombre
        FROM conciliaciones c
        JOIN gasolineras g ON g.id = c.gasolinera_id
        JOIN usuarios u ON u.id = c.responsable_id
        {where}
        ORDER BY c.fecha DESC, c.id DESC
    """, params)
    lista = cur.fetchall()

    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()
    conn.close()

    return render_template(
        "conciliacion/listado.html",
        lista=lista,
        gasolineras=gasolineras,
        filtro_gasolinera=filtro_gasolinera,
        filtro_estado=filtro_estado,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        estados_conciliacion=ESTADOS_CONCILIACION,
        turno_labels=TURNOS_CONCILIACION_LABELS,
    )


# ── Detalle ───────────────────────────────────────────────────────────────────

@conciliacion_bp.route("/<int:id>")
def detalle(id):
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.*,
               g.nombre AS gasolinera_nombre,
               u.nombre AS responsable_nombre
        FROM conciliaciones c
        JOIN gasolineras g ON g.id = c.gasolinera_id
        JOIN usuarios u ON u.id = c.responsable_id
        WHERE c.id = ?
    """, (id,))
    conciliacion = cur.fetchone()
    conn.close()

    if not conciliacion:
        return redirect("/conciliacion")

    return render_template(
        "conciliacion/detalle.html",
        conciliacion=conciliacion,
        turno_labels=TURNOS_CONCILIACION_LABELS,
    )


# ── Crear ─────────────────────────────────────────────────────────────────────

@conciliacion_bp.route("/crear", methods=["GET", "POST"])
def crear():
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre FROM gasolineras WHERE estado = 'activo' ORDER BY nombre ASC")
    gasolineras = cur.fetchall()

    gasolinera_id_pre = request.args.get("gasolinera_id", "").strip()
    fecha_pre = request.args.get("fecha", date.today().isoformat()).strip()

    datos_calculados = None
    gasolinera_pre_row = None
    habs_detalle = []
    n_sin_despacho = 0

    if gasolinera_id_pre and fecha_pre:
        try:
            total_entrada, total_despachado = _calcular_totales(cur, gasolinera_id_pre, fecha_pre)
            datos_calculados = {
                "total_entrada_l": total_entrada,
                "total_despachado_l": total_despachado,
            }
            cur.execute("SELECT nombre FROM gasolineras WHERE id = ?", (gasolinera_id_pre,))
            gasolinera_pre_row = cur.fetchone()
            habs_detalle = _detalle_habilitaciones(cur, gasolinera_id_pre, fecha_pre)
            n_sin_despacho = sum(
                1 for h in habs_detalle
                if h["estado"] in ("pendiente", "aprobada")
            )
        except Exception:
            pass

    conn.close()

    error = None

    if request.method == "POST":
        gasolinera_id = request.form.get("gasolinera_id", "").strip()
        fecha = request.form.get("fecha", "").strip()
        turno = request.form.get("turno", "").strip() or None
        inicio_str = request.form.get("saldo_fisico_inicio_l", "0").strip()
        fin_str = request.form.get("saldo_fisico_fin_l", "0").strip()
        observaciones = request.form.get("observaciones", "").strip()

        if not gasolinera_id:
            error = "Debe seleccionar una gasolinera."
        elif not fecha:
            error = "La fecha es obligatoria."
        else:
            try:
                saldo_inicio = float(inicio_str)
                saldo_fin = float(fin_str)
            except ValueError:
                error = "Los saldos físicos deben ser números válidos."
                saldo_inicio = saldo_fin = 0.0

        if not error:
            conn = conectar()
            cur = conn.cursor()
            total_entrada, total_despachado = _calcular_totales(cur, gasolinera_id, fecha)

            diferencia_l = saldo_fin - (saldo_inicio + total_entrada - total_despachado)

            if total_despachado > 0.001:
                diferencia_pct = abs(diferencia_l) / total_despachado
            else:
                diferencia_pct = 0.0

            if diferencia_pct > _DIFF_TOLERANCIA:
                estado = "con_alerta"
                if not observaciones:
                    error = (
                        f"La diferencia ({diferencia_pct:.2%}) supera el 0.5%. "
                        f"Las observaciones son obligatorias."
                    )
                    conn.close()
            else:
                estado = "cerrada"

        if not error:
            cur.execute("""
                INSERT INTO conciliaciones
                    (gasolinera_id, fecha, turno, saldo_fisico_inicio_l, saldo_fisico_fin_l,
                     total_entrada_l, total_despachado_l, diferencia_l, diferencia_porcentaje,
                     estado, observaciones, responsable_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (gasolinera_id, fecha, turno, saldo_inicio, saldo_fin,
                  total_entrada, total_despachado, diferencia_l, diferencia_pct,
                  estado, observaciones or None, session.get("user_id")))
            nuevo_id = cur.lastrowid
            conn.commit()
            conn.close()
            return redirect(f"/conciliacion/{nuevo_id}?ok=1")

    return render_template(
        "conciliacion/crear.html",
        error=error,
        gasolineras=gasolineras,
        gasolinera_id_pre=gasolinera_id_pre,
        gasolinera_pre_row=gasolinera_pre_row,
        fecha_pre=fecha_pre,
        datos_calculados=datos_calculados,
        habs_detalle=habs_detalle,
        n_sin_despacho=n_sin_despacho,
        hoy=date.today().isoformat(),
        turnos=TURNOS_CONCILIACION,
        turno_labels=TURNOS_CONCILIACION_LABELS,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )
