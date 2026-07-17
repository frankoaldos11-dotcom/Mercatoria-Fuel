from flask import Blueprint, render_template, request, redirect, session

from database import conectar
from utils.auth import requiere_login
from utils.constants import ROLES_ADMIN_PM, TIPOS_COMBUSTIBLE, TIPOS_COMBUSTIBLE_LABELS

mermas_bp = Blueprint("mermas", __name__, url_prefix="/mermas")


def _requiere_admin_pm():
    return session.get("rol") not in ROLES_ADMIN_PM


# ── Vista acumulada de mermas (recepción por puerto, recepción directa y
# transferencia depósito→gasolinera) — solo lectura, mismo criterio de signo
# en las tres fuentes: esperado − real (positivo = pérdida). ─────────────────

@mermas_bp.route("/")
def listado():
    redir = requiere_login()
    if redir:
        return redir
    if _requiere_admin_pm():
        return redirect("/dashboard?access_error=Acceso+restringido+a+admin+y+puesto_de_mando")

    filtro_desde = request.args.get("desde", "").strip()
    filtro_hasta = request.args.get("hasta", "").strip()
    filtro_origen = request.args.get("origen", "").strip()
    filtro_combustible = request.args.get("combustible", "").strip()

    conn = conectar()
    cur = conn.cursor()

    cond_puerto = ["lp.estado = 'transferido'", "lp.litros_recibidos IS NOT NULL"]
    params_puerto = []
    cond_recepcion = ["r.estado = 'confirmada'"]
    params_recepcion = []
    cond_transf = ["t.estado = 'recibida'", "t.litros_recibidos IS NOT NULL"]
    params_transf = []

    if filtro_desde:
        cond_puerto.append("lp.fecha_transferencia >= ?")
        params_puerto.append(filtro_desde)
        cond_recepcion.append("r.fecha >= ?")
        params_recepcion.append(filtro_desde)
        cond_transf.append("t.fecha_llegada >= ?")
        params_transf.append(filtro_desde)
    if filtro_hasta:
        cond_puerto.append("lp.fecha_transferencia <= ?")
        params_puerto.append(filtro_hasta)
        cond_recepcion.append("r.fecha <= ?")
        params_recepcion.append(filtro_hasta)
        cond_transf.append("t.fecha_llegada <= ?")
        params_transf.append(filtro_hasta)
    if filtro_combustible:
        cond_puerto.append("lp.tipo_combustible = ?")
        params_puerto.append(filtro_combustible)
        cond_recepcion.append("r.tipo_combustible = ?")
        params_recepcion.append(filtro_combustible)
        cond_transf.append("t.tipo_combustible = ?")
        params_transf.append(filtro_combustible)

    filas = []

    if filtro_origen in ("", "recepcion_puerto"):
        cur.execute(f"""
            SELECT lp.fecha_transferencia AS fecha, 'recepcion_puerto' AS origen,
                   ('Isotanque ' || lp.numero_isotanque || ' — ' || p.nombre) AS referencia,
                   lp.tipo_combustible AS tipo_combustible,
                   lp.litros AS esperado, lp.litros_recibidos AS real,
                   lp.merma_l AS merma, lp.id AS registro_id
            FROM llegadas_puerto lp
            JOIN puertos p ON p.id = lp.puerto_id
            WHERE {" AND ".join(cond_puerto)}
            ORDER BY lp.fecha_transferencia DESC
        """, params_puerto)
        filas.extend(cur.fetchall())

    if filtro_origen in ("", "recepcion_directa"):
        cur.execute(f"""
            SELECT r.fecha AS fecha, 'recepcion_directa' AS origen,
                   (r.proveedor || COALESCE(' — Vale ' || r.no_vale, '')) AS referencia,
                   r.tipo_combustible AS tipo_combustible,
                   r.litros_factura AS esperado, r.litros_recibidos AS real,
                   (r.litros_factura - r.litros_recibidos) AS merma, r.id AS registro_id
            FROM recepciones r
            WHERE {" AND ".join(cond_recepcion)}
            ORDER BY r.fecha DESC
        """, params_recepcion)
        filas.extend(cur.fetchall())

    if filtro_origen in ("", "transferencia"):
        cur.execute(f"""
            SELECT t.fecha_llegada AS fecha, 'transferencia' AS origen,
                   (d.nombre || ' → ' || g.nombre) AS referencia,
                   t.tipo_combustible AS tipo_combustible,
                   t.litros_solicitados AS esperado, t.litros_recibidos AS real,
                   (t.litros_solicitados - t.litros_recibidos) AS merma, t.id AS registro_id
            FROM transferencias t
            JOIN depositos d ON d.id = t.deposito_origen_id
            JOIN gasolineras g ON g.id = t.gasolinera_destino_id
            WHERE {" AND ".join(cond_transf)}
            ORDER BY t.fecha_llegada DESC
        """, params_transf)
        filas.extend(cur.fetchall())

    conn.close()

    filas.sort(key=lambda f: f["fecha"] or "", reverse=True)

    total_merma = sum(float(f["merma"] or 0) for f in filas)
    total_por_origen = {}
    for f in filas:
        total_por_origen[f["origen"]] = total_por_origen.get(f["origen"], 0.0) + float(f["merma"] or 0)

    return render_template(
        "mermas/listado.html",
        filas=filas,
        total_merma=total_merma,
        total_por_origen=total_por_origen,
        filtro_desde=filtro_desde,
        filtro_hasta=filtro_hasta,
        filtro_origen=filtro_origen,
        filtro_combustible=filtro_combustible,
        tipos_combustible=TIPOS_COMBUSTIBLE,
        combustible_labels=TIPOS_COMBUSTIBLE_LABELS,
    )
