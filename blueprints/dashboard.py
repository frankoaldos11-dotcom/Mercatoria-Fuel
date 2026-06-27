from flask import Blueprint, render_template, session, redirect
from database import conectar

dashboard_bp = Blueprint("dashboard", __name__)


def _requiere_login():
    return "usuario" not in session


@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def dashboard():
    if _requiere_login():
        return redirect("/login")

    conn = conectar()
    cur = conn.cursor()

    # Inventario total: suma de litros_reservados en subinventarios activos
    cur.execute("""
        SELECT COALESCE(SUM(litros_reservados), 0) AS total
        FROM subinventarios
        WHERE activo = 1
    """)
    inventario_total = cur.fetchone()["total"] or 0

    # Inventario reservado: subinventarios de tipo cliente
    cur.execute("""
        SELECT COALESCE(SUM(litros_reservados), 0) AS total
        FROM subinventarios
        WHERE activo = 1 AND tipo = 'cliente'
    """)
    inventario_reservado = cur.fetchone()["total"] or 0

    disponible_venta = max(0, inventario_total - inventario_reservado)

    # Tarjetas con bajo saldo — tabla futura; por ahora 0
    tarjetas_bajo_saldo = 0

    # Conciliaciones pendientes — tabla futura; por ahora 0
    conciliaciones_pendientes = 0

    # Despachos pendientes — movimientos de tipo despacho sin completar; por ahora 0
    cur.execute("""
        SELECT COUNT(*) AS total FROM movimientos WHERE tipo = 'despacho'
    """)
    despachos_pendientes = cur.fetchone()["total"] or 0

    # Transferencias en tránsito — por ahora 0
    transferencias_transito = 0

    # Alertas críticas — por ahora 0
    alertas_criticas = 0

    # Gasolineras activas
    cur.execute("SELECT COUNT(*) AS total FROM gasolineras WHERE estado = 'activo'")
    gasolineras_activas = cur.fetchone()["total"] or 0

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
    )
