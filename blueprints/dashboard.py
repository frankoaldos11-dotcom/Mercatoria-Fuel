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

    cur.execute("""
        SELECT COALESCE(SUM(litros_reservados), 0) AS total
        FROM subinventarios
        WHERE activo = 1
    """)
    inventario_total = cur.fetchone()["total"] or 0

    cur.execute("""
        SELECT COALESCE(SUM(litros_reservados), 0) AS total
        FROM subinventarios
        WHERE activo = 1 AND tipo = 'cliente'
    """)
    inventario_reservado = cur.fetchone()["total"] or 0

    disponible_venta = max(0, inventario_total - inventario_reservado)

    tarjetas_bajo_saldo = 0
    conciliaciones_pendientes = 0

    cur.execute("SELECT COUNT(*) AS total FROM movimientos WHERE tipo = 'despacho'")
    despachos_pendientes = cur.fetchone()["total"] or 0

    transferencias_transito = 0
    alertas_criticas = 0

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
