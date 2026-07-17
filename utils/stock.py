def stock_deposito_por_tipo(cur, deposito_id):
    """Stock del depósito agrupado por tipo_combustible — {tipo: litros}.
    Cálculo base: todo lo demás que necesite stock de depósito se apoya en este.
    Filas legacy con tipo_combustible NULL (previas a este cambio, o cualquier
    caso no contemplado) se agrupan bajo la clave None en vez de romper —
    quedan fuera de cualquier tipo real, pero no se pierden del total."""
    cur.execute("""
        SELECT tipo_combustible,
               COALESCE(SUM(
                   CASE WHEN tipo = 'transferencia_salida' THEN -litros ELSE litros END
               ), 0) AS stock
        FROM movimientos
        WHERE deposito_id = ?
        AND tipo IN ('recepcion', 'transferencia_salida', 'transferencia_anulacion')
        GROUP BY tipo_combustible
    """, (deposito_id,))
    return {row["tipo_combustible"]: float(row["stock"] or 0) for row in cur.fetchall()}


def stock_deposito(cur, deposito_id, tipo_combustible=None):
    """Stock del depósito. Sin tipo_combustible: total agregado (todos los
    tipos, compatibilidad con los callers que genuinamente necesitan el total).
    Con tipo_combustible: stock de ESE tipo únicamente — es lo que debe usar
    cualquier validación de disponibilidad antes de sacar litros de un tipo
    específico."""
    por_tipo = stock_deposito_por_tipo(cur, deposito_id)
    if tipo_combustible is not None:
        return por_tipo.get(tipo_combustible, 0.0)
    return sum(por_tipo.values())


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
