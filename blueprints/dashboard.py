from datetime import date, timedelta

from flask import Blueprint, render_template
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

    # Inventario total: stock real de todas las gasolineras (transferencias_entrada confirmadas)
    cur.execute("""
        SELECT COALESCE(SUM(litros), 0) AS total
        FROM movimientos
        WHERE tipo = 'transferencia_entrada'
    """)
    inventario_total = cur.fetchone()["total"] or 0

    # Inventario reservado (subinventarios cliente — placeholder hasta Sprint 5)
    cur.execute("""
        SELECT COALESCE(SUM(litros_reservados), 0) AS total
        FROM subinventarios
        WHERE activo = 1 AND tipo = 'cliente'
    """)
    inventario_reservado = cur.fetchone()["total"] or 0

    disponible_venta = max(0, inventario_total - inventario_reservado)

    # Tarjetas activas con saldo_usable_l < 200 L
    cur.execute("""
        SELECT COUNT(*) AS total FROM tarjetas
        WHERE estado = 'activa' AND saldo_usable_l < 200
    """)
    tarjetas_bajo_saldo = cur.fetchone()["total"] or 0

    # Conciliaciones pendientes: gasolineras con despachos hoy sin conciliación cerrada
    hoy_str = date.today().isoformat()
    manana_str = (date.today() + timedelta(days=1)).isoformat()
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

    # Despachos pendientes: habilitaciones aprobadas sin despacho completado
    cur.execute("""
        SELECT COUNT(*) AS total FROM habilitaciones h
        WHERE h.estado = 'aprobada'
        AND NOT EXISTS (
            SELECT 1 FROM despachos d
            WHERE d.habilitacion_id = h.id AND d.estado = 'completado'
        )
    """)
    despachos_pendientes = cur.fetchone()["total"] or 0

    # Combustible en tránsito: transferencias en_transito
    cur.execute("""
        SELECT COALESCE(SUM(litros_solicitados), 0) AS total
        FROM transferencias
        WHERE estado = 'en_transito'
    """)
    transferencias_transito = cur.fetchone()["total"] or 0

    # Alertas: devoluciones vencidas + conciliaciones con_alerta últimos 7 días
    hace_7_dias = (date.today() - timedelta(days=7)).isoformat()
    cur.execute("""
        SELECT COUNT(*) AS total FROM devoluciones_tarjetas
        WHERE estado = 'pendiente'
        AND fecha_estimada_liberacion IS NOT NULL
        AND fecha_estimada_liberacion <= ?
    """, (date.today().isoformat(),))
    alertas_dev = cur.fetchone()["total"] or 0
    cur.execute("""
        SELECT COUNT(*) AS total FROM conciliaciones
        WHERE estado = 'con_alerta' AND fecha >= ?
    """, (hace_7_dias,))
    alertas_concil = cur.fetchone()["total"] or 0
    alertas_criticas = alertas_dev + alertas_concil

    cur.execute("SELECT COUNT(*) AS total FROM gasolineras WHERE estado = 'activo'")
    gasolineras_activas = cur.fetchone()["total"] or 0

    # Licencias vencidas o por vencer en 30 días
    limite_30 = (date.today() + timedelta(days=30)).isoformat()
    cur.execute("""
        SELECT COUNT(*) AS total FROM choferes
        WHERE estado = 'activo'
        AND licencia_vencimiento IS NOT NULL
        AND licencia_vencimiento <= ?
    """, (limite_30,))
    licencias_por_vencer = cur.fetchone()["total"] or 0

    conn.close()

    return render_template(
        "dashboard.html",
        inventario_total=inventario_total,
        inventario_reservado=inventario_reservado,
        disponible_venta=disponible_venta,
        tarjetas_bajo_saldo=tarjetas_bajo_saldo,
        conciliaciones_pendientes=conciliaciones_pendientes,
        despachos_pendientes=despachos_pendientes,
        transferencias_transito=transferencias_transito,
        alertas_criticas=alertas_criticas,
        gasolineras_activas=gasolineras_activas,
        licencias_por_vencer=licencias_por_vencer,
    )
