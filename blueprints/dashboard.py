from datetime import date, timedelta

from flask import Blueprint, render_template, session
from database import conectar
from utils.auth import requiere_login

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
def dashboard():
    redir = requiere_login()
    if redir:
        return redir

    conn = conectar()
    cur = conn.cursor()

    hoy = date.today()
    hoy_str = hoy.isoformat()
    manana_str = (hoy + timedelta(days=1)).isoformat()
    hace_7_dias = (hoy - timedelta(days=7)).isoformat()
    limite_30 = (hoy + timedelta(days=30)).isoformat()
    mes_inicio = hoy.replace(day=1).isoformat()
    if hoy.month == 12:
        mes_fin = hoy.replace(year=hoy.year + 1, month=1, day=1).isoformat()
    else:
        mes_fin = hoy.replace(month=hoy.month + 1, day=1).isoformat()

    # ── Fila 1: Inventario ────────────────────────────────────────────────────
    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS total FROM movimientos
        WHERE tipo = 'transferencia_entrada'
    """)
    inventario_total = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COALESCE(SUM(litros_reservados), 0) AS total
        FROM subinventarios WHERE activo = 1 AND tipo = 'cliente'
    """)
    inventario_reservado = cur.fetchone()["total"] or 0

    disponible_venta = max(0, inventario_total - inventario_reservado)

    cur.execute("""
        SELECT COALESCE(SUM(litros_solicitados), 0) AS total
        FROM transferencias WHERE estado = 'en_transito'
    """)
    combustible_transito = cur.fetchone()["total"] or 0

    # ── Fila 2: Operativa ─────────────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*) AS total FROM tarjetas
        WHERE estado = 'activa' AND saldo_usable_l < 200
    """)
    tarjetas_bajo_saldo = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(*) AS total FROM devoluciones_tarjetas
        WHERE estado = 'pendiente'
    """)
    devoluciones_pendientes = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(*) AS total FROM habilitaciones h
        WHERE h.estado = 'aprobada'
        AND NOT EXISTS (
            SELECT 1 FROM despachos d
            WHERE d.habilitacion_id = h.id AND d.estado = 'completado'
        )
    """)
    despachos_pendientes = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(DISTINCT g.id) AS total FROM gasolineras g
        WHERE g.estado = 'activo'
        AND EXISTS (
            SELECT 1 FROM movimientos m
            WHERE m.gasolinera_id = g.id AND m.tipo = 'despacho'
            AND m.fecha >= ? AND m.fecha < ?
        )
        AND NOT EXISTS (
            SELECT 1 FROM conciliaciones c
            WHERE c.gasolinera_id = g.id AND c.fecha = ?
            AND c.estado IN ('cerrada', 'con_alerta')
        )
    """, (hoy_str, manana_str, hoy_str))
    conciliaciones_pendientes = cur.fetchone()["total"] or 0

    # ── Fila 3: Alertas ───────────────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*) AS total FROM choferes
        WHERE estado = 'activo'
        AND licencia_vencimiento IS NOT NULL
        AND licencia_vencimiento <= ?
    """, (limite_30,))
    licencias_por_vencer = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(*) AS total FROM conciliaciones
        WHERE estado = 'con_alerta' AND fecha >= ?
    """, (hace_7_dias,))
    conciliaciones_con_alerta = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COUNT(*) AS total FROM devoluciones_tarjetas
        WHERE estado = 'pendiente'
        AND fecha_estimada_liberacion IS NOT NULL
        AND fecha_estimada_liberacion <= ?
    """, (hoy_str,))
    alertas_dev_vencidas = cur.fetchone()["total"] or 0
    alertas_criticas = alertas_dev_vencidas + conciliaciones_con_alerta

    # ── Gasolineras activas ───────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) AS total FROM gasolineras WHERE estado = 'activo'")
    gasolineras_activas = cur.fetchone()["total"] or 0

    # ── Actividad reciente: últimos 10 despachos ──────────────────────────────
    cur.execute("""
        SELECT d.fecha_despacho, cl.nombre AS cliente, v.chapa,
               g.nombre AS gasolinera, d.litros_despachados
        FROM despachos d
        JOIN clientes cl ON cl.id = d.cliente_id
        JOIN vehiculos v ON v.id = d.unidad_id
        JOIN gasolineras g ON g.id = d.gasolinera_id
        WHERE d.estado = 'completado'
        ORDER BY d.created_at DESC LIMIT 10
    """)
    despachos_recientes = cur.fetchall()

    # ── Top 5 clientes por consumo del mes ───────────────────────────────────
    cur.execute("""
        SELECT cl.nombre, COALESCE(SUM(d.litros_despachados), 0) AS total
        FROM clientes cl
        LEFT JOIN despachos d ON d.cliente_id = cl.id AND d.estado = 'completado'
            AND d.fecha_despacho >= ? AND d.fecha_despacho < ?
        WHERE cl.activo = 1
        GROUP BY cl.id, cl.nombre
        ORDER BY total DESC LIMIT 5
    """, (mes_inicio, mes_fin))
    top_clientes = cur.fetchall()

    # ── Vista por rol ─────────────────────────────────────────────────────────
    rol = session.get("rol", "")

    if rol in ("operario", "operario_gasolinera"):
        cur.execute("""
            SELECT h.id, h.litros_autorizados, h.fecha_habilitacion,
                   cli.nombre AS cliente, v.chapa, g.nombre AS gasolinera,
                   t.numero_parcial AS tarjeta
            FROM habilitaciones h
            JOIN clientes cli ON cli.id = h.cliente_id
            JOIN vehiculos v ON v.id = h.unidad_id
            JOIN gasolineras g ON g.id = h.gasolinera_id
            JOIN tarjetas t ON t.id = h.tarjeta_id
            WHERE h.estado = 'aprobada'
            AND NOT EXISTS (
                SELECT 1 FROM despachos d
                WHERE d.habilitacion_id = h.id AND d.estado = 'completado'
            )
            ORDER BY h.fecha_habilitacion ASC LIMIT 20
        """)
        habs_pendientes = cur.fetchall()
        conn.close()
        return render_template(
            "dashboard_operario.html",
            despachos_pendientes=despachos_pendientes,
            habs_pendientes=habs_pendientes,
        )

    if rol == "operario_deposito":
        cur.execute("""
            SELECT lp.id, lp.numero_isotanque, lp.tipo_combustible,
                   lp.litros, lp.fecha_llegada,
                   p.nombre AS puerto_nombre
            FROM llegadas_puerto lp
            JOIN puertos p ON p.id = lp.puerto_id
            WHERE lp.estado = 'en_puerto'
            ORDER BY lp.fecha_llegada ASC LIMIT 20
        """)
        llegadas_pendientes = cur.fetchall()
        conn.close()
        return render_template(
            "dashboard_operario_deposito.html",
            llegadas_pendientes=llegadas_pendientes,
        )

    conn.close()

    if rol == "supervisor":
        return render_template(
            "dashboard_supervisor.html",
            inventario_total=inventario_total,
            inventario_reservado=inventario_reservado,
            disponible_venta=disponible_venta,
            combustible_transito=combustible_transito,
            tarjetas_bajo_saldo=tarjetas_bajo_saldo,
            devoluciones_pendientes=devoluciones_pendientes,
            despachos_pendientes=despachos_pendientes,
            conciliaciones_pendientes=conciliaciones_pendientes,
            licencias_por_vencer=licencias_por_vencer,
            conciliaciones_con_alerta=conciliaciones_con_alerta,
            alertas_criticas=alertas_criticas,
            gasolineras_activas=gasolineras_activas,
        )

    return render_template(
        "dashboard.html",
        # Inventario
        inventario_total=inventario_total,
        inventario_reservado=inventario_reservado,
        disponible_venta=disponible_venta,
        combustible_transito=combustible_transito,
        # Operativa
        tarjetas_bajo_saldo=tarjetas_bajo_saldo,
        devoluciones_pendientes=devoluciones_pendientes,
        despachos_pendientes=despachos_pendientes,
        conciliaciones_pendientes=conciliaciones_pendientes,
        # Alertas
        licencias_por_vencer=licencias_por_vencer,
        conciliaciones_con_alerta=conciliaciones_con_alerta,
        alertas_criticas=alertas_criticas,
        # Otros
        gasolineras_activas=gasolineras_activas,
        # Actividad
        despachos_recientes=despachos_recientes,
        top_clientes=top_clientes,
        # Mantener compatibilidad con template anterior
        transferencias_transito=combustible_transito,
    )
