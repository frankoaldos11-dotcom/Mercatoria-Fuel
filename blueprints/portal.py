import io
from datetime import date

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from flask import Blueprint, render_template, request, redirect, session, send_file

from database import conectar

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


def _requiere_cliente():
    if "usuario" not in session:
        return redirect("/login")
    if session.get("rol") != "cliente":
        return redirect("/dashboard")
    if not session.get("cliente_id"):
        return redirect("/login")
    return None


def _cliente_id():
    return session["cliente_id"]


# ── Dashboard del cliente ─────────────────────────────────────────────────────

@portal_bp.route("/")
def dashboard():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    hoy = date.today()
    mes_inicio = hoy.replace(day=1).isoformat()
    if hoy.month == 12:
        mes_fin = hoy.replace(year=hoy.year + 1, month=1, day=1).isoformat()
    else:
        mes_fin = hoy.replace(month=hoy.month + 1, day=1).isoformat()
    anio_inicio = hoy.replace(month=1, day=1).isoformat()
    anio_fin = hoy.replace(year=hoy.year + 1, month=1, day=1).isoformat()

    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT cl.nombre FROM clientes cl WHERE cl.id = ?
    """, (cid,))
    cliente = cur.fetchone()

    cur.execute("""
        SELECT COALESCE(SUM(d.litros_despachados), 0) AS total
        FROM despachos d
        WHERE d.cliente_id = ? AND d.estado = 'completado'
        AND d.fecha_despacho >= ? AND d.fecha_despacho < ?
    """, (cid, mes_inicio, mes_fin))
    consumo_mes = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COALESCE(SUM(d.litros_despachados), 0) AS total
        FROM despachos d
        WHERE d.cliente_id = ? AND d.estado = 'completado'
        AND d.fecha_despacho >= ? AND d.fecha_despacho < ?
    """, (cid, anio_inicio, anio_fin))
    consumo_anio = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(*) AS total FROM habilitaciones
        WHERE cliente_id = ? AND estado IN ('pendiente', 'aprobada')
    """, (cid,))
    habilitaciones_activas = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(*) AS total FROM despachos
        WHERE cliente_id = ? AND estado = 'completado'
        AND fecha_despacho >= ? AND fecha_despacho < ?
    """, (cid, mes_inicio, mes_fin))
    despachos_mes = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COALESCE(SUM(s.litros_reservados), 0) AS total
        FROM subinventarios s
        WHERE s.cliente_id = ? AND s.activo = 1
    """, (cid,))
    saldo_subinventario = cur.fetchone()["total"] or 0

    conn.close()

    return render_template(
        "portal/dashboard.html",
        cliente=cliente,
        consumo_mes=consumo_mes,
        consumo_anio=consumo_anio,
        habilitaciones_activas=habilitaciones_activas,
        despachos_mes=despachos_mes,
        saldo_subinventario=saldo_subinventario,
    )


# ── Historial de despachos ────────────────────────────────────────────────────

@portal_bp.route("/despachos")
def despachos():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    filtro_desde = request.args.get("desde", "")
    filtro_hasta = request.args.get("hasta", "")
    filtro_chapa = request.args.get("chapa", "")
    exportar = request.args.get("exportar", "")

    conds = ["d.cliente_id = ?", "d.estado = 'completado'"]
    params = [cid]
    if filtro_desde:
        conds.append("d.fecha_despacho >= ?")
        params.append(filtro_desde)
    if filtro_hasta:
        conds.append("d.fecha_despacho <= ?")
        params.append(filtro_hasta)
    if filtro_chapa:
        conds.append("v.chapa LIKE ?")
        params.append(f"%{filtro_chapa}%")

    where = "WHERE " + " AND ".join(conds)

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT d.fecha_despacho, v.chapa, ch.nombre AS chofer,
               g.nombre AS gasolinera, d.litros_despachados, d.foto_ticket_url
        FROM despachos d
        JOIN vehiculos v ON v.id = d.unidad_id
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        JOIN gasolineras g ON g.id = d.gasolinera_id
        {where}
        ORDER BY d.fecha_despacho DESC
    """, params)
    filas = cur.fetchall()
    conn.close()

    if exportar == "excel":
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Despachos"
        ws.append(["Fecha", "Chapa", "Chofer", "Gasolinera", "Litros"])
        for f in filas:
            ws.append([f["fecha_despacho"], f["chapa"], f["chofer"] or "",
                       f["gasolinera"], f["litros_despachados"]])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name="mis_despachos.xlsx")

    return render_template("portal/despachos.html", filas=filas,
                           filtro_desde=filtro_desde, filtro_hasta=filtro_hasta,
                           filtro_chapa=filtro_chapa)


# ── Consumo mensual (Chart.js) ────────────────────────────────────────────────

@portal_bp.route("/consumo-mensual")
def consumo_mensual():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    conn = conectar()
    cur = conn.cursor()

    cur.execute("""
        SELECT SUBSTR(d.fecha_despacho, 1, 7) AS mes,
               COALESCE(SUM(d.litros_despachados), 0) AS total
        FROM despachos d
        WHERE d.cliente_id = ? AND d.estado = 'completado'
        AND d.fecha_despacho >= ?
        GROUP BY mes
        ORDER BY mes
    """, (cid, str(date.today().year - 1) + "-01-01"))
    datos = cur.fetchall()
    conn.close()

    labels = [r["mes"] for r in datos]
    valores = [r["total"] for r in datos]

    return render_template("portal/consumo_mensual.html", labels=labels, valores=valores)


# ── Consumo por vehículo ──────────────────────────────────────────────────────

@portal_bp.route("/consumo-vehiculo")
def consumo_vehiculo():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.chapa, v.marca, v.modelo,
               COALESCE(SUM(d.litros_despachados), 0) AS total,
               COALESCE(COUNT(DISTINCT SUBSTR(d.fecha_despacho, 1, 7)), 1) AS meses_activos
        FROM vehiculos v
        LEFT JOIN despachos d ON d.unidad_id = v.id AND d.estado = 'completado'
        WHERE v.cliente_id = ?
        GROUP BY v.id, v.chapa, v.marca, v.modelo
        ORDER BY total DESC
    """, (cid,))
    datos = cur.fetchall()
    conn.close()

    return render_template("portal/consumo_vehiculo.html", datos=datos)


# ── Consumo por chofer ────────────────────────────────────────────────────────

@portal_bp.route("/consumo-chofer")
def consumo_chofer():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(ch.nombre, 'Sin asignar') AS chofer,
               COALESCE(SUM(d.litros_despachados), 0) AS total
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        LEFT JOIN despachos d ON d.unidad_id = v.id AND d.estado = 'completado'
        WHERE v.cliente_id = ?
        GROUP BY ch.nombre
        ORDER BY total DESC
    """, (cid,))
    datos = cur.fetchall()
    conn.close()

    return render_template("portal/consumo_chofer.html", datos=datos)


# ── Mis vehículos y choferes ──────────────────────────────────────────────────

@portal_bp.route("/unidades")
def unidades():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    conn = conectar()
    cur = conn.cursor()
    cur.execute("""
        SELECT v.chapa, v.marca, v.modelo, v.tipo_combustible, v.estado,
               ch.nombre AS chofer, ch.licencia_numero, ch.licencia_vencimiento
        FROM vehiculos v
        LEFT JOIN choferes ch ON ch.id = v.chofer_id
        WHERE v.cliente_id = ?
        ORDER BY v.chapa
    """, (cid,))
    datos = cur.fetchall()
    conn.close()

    hoy = date.today().isoformat()
    limite_30 = (date.today().replace(day=date.today().day)).isoformat()

    return render_template("portal/unidades.html", datos=datos, hoy=hoy)


# ── Mis habilitaciones ────────────────────────────────────────────────────────

@portal_bp.route("/habilitaciones")
def habilitaciones():
    redir = _requiere_cliente()
    if redir:
        return redir

    cid = _cliente_id()
    filtro_estado = request.args.get("estado", "")

    conds = ["h.cliente_id = ?"]
    params = [cid]
    if filtro_estado:
        conds.append("h.estado = ?")
        params.append(filtro_estado)

    where = "WHERE " + " AND ".join(conds)

    conn = conectar()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT h.id, h.fecha_habilitacion, h.fecha_vencimiento,
               h.litros_autorizados, h.litros_despachados, h.estado,
               v.chapa, g.nombre AS gasolinera
        FROM habilitaciones h
        JOIN vehiculos v ON v.id = h.unidad_id
        JOIN gasolineras g ON g.id = h.gasolinera_id
        {where}
        ORDER BY h.fecha_habilitacion DESC
    """, params)
    datos = cur.fetchall()
    conn.close()

    from utils.constants import ESTADOS_HABILITACION_LABELS
    return render_template("portal/habilitaciones.html", datos=datos,
                           estados=ESTADOS_HABILITACION_LABELS,
                           filtro_estado=filtro_estado)
