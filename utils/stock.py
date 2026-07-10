def stock_deposito(cur, deposito_id):
    cur.execute("""
        SELECT COALESCE(SUM(
            CASE WHEN tipo = 'transferencia_salida' THEN -litros ELSE litros END
        ), 0) AS stock
        FROM movimientos
        WHERE deposito_id = ?
        AND tipo IN ('recepcion', 'transferencia_salida', 'transferencia_anulacion')
    """, (deposito_id,))
    return float(cur.fetchone()["stock"] or 0)


def stock_gasolinera(cur, gasolinera_id):
    cur.execute("""
        SELECT COALESCE(SUM(CASE WHEN tipo = 'transferencia_entrada' THEN litros
                                  WHEN tipo = 'despacho' THEN -litros
                                  ELSE 0 END), 0) AS stock
        FROM movimientos
        WHERE gasolinera_id = ?
          AND tipo IN ('transferencia_entrada', 'despacho')
    """, (gasolinera_id,))
    return float(cur.fetchone()["stock"] or 0)
