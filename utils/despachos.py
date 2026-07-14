from datetime import datetime, timedelta

_MAX_INTENTOS = 20


def _candidato_numero_operacion(cur, gasolinera_id, fecha_despacho):
    """AAAAMMDD + id_gasolinera (2 dígitos) + secuencia_del_día (4 dígitos).
    La secuencia es COUNT(despachos de esa gasolinera ese día) + 1 — correcta
    en el caso normal; la unicidad real la garantiza el índice UNIQUE de la
    columna, con reintento en insertar_despacho_con_numero() ante colisión."""
    fecha_str = str(fecha_despacho)[:10]
    fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    fecha_fin = (fecha_dt + timedelta(days=1)).isoformat()

    cur.execute("""
        SELECT COUNT(*) AS n FROM despachos
        WHERE gasolinera_id = ? AND fecha_despacho >= ? AND fecha_despacho < ?
    """, (gasolinera_id, fecha_str, fecha_fin))
    secuencia = (cur.fetchone()["n"] or 0) + 1

    aaaammdd = fecha_str.replace("-", "")
    return f"{aaaammdd}{int(gasolinera_id):02d}{secuencia:04d}"


def insertar_despacho_con_numero(cur, sql, params, gasolinera_id, fecha_despacho):
    """Ejecuta `sql` (un INSERT INTO despachos cuyo ÚLTIMO placeholder `?` es
    numero_operacion) con `params` + el número generado, dentro de la
    transacción/cursor en curso. Si la inserción choca con el UNIQUE de
    numero_operacion (carrera entre despachos concurrentes de la misma
    gasolinera y día), reintenta con el siguiente número disponible — nunca
    deja que la colisión rompa el despacho.

    Devuelve (lastrowid, numero_operacion).
    """
    ultimo_error = None
    for _ in range(_MAX_INTENTOS):
        numero = _candidato_numero_operacion(cur, gasolinera_id, fecha_despacho)
        cur.execute("SAVEPOINT sp_numero_operacion")
        try:
            cur.execute(sql, params + (numero,))
        except Exception as e:
            cur.execute("ROLLBACK TO SAVEPOINT sp_numero_operacion")
            ultimo_error = e
            continue
        cur.execute("RELEASE SAVEPOINT sp_numero_operacion")
        return cur.lastrowid, numero
    raise ultimo_error
