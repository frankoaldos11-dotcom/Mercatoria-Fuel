from utils.stock import stock_gasolinera


class SubinventarioError(Exception):
    """Se lanza cuando una operación de subinventario violaría el tope de stock físico."""


def validar_tope_reserva(cur, gasolinera_id, litros_propuestos, excluir_id=None):
    """Lanza SubinventarioError si `litros_propuestos` (sumado a los demás subinventarios
    activos de la gasolinera, excluyendo opcionalmente uno) superaría el stock físico."""
    stock_actual = stock_gasolinera(cur, gasolinera_id)
    if excluir_id:
        cur.execute("""
            SELECT COALESCE(SUM(litros_reservados), 0) AS total
            FROM subinventarios WHERE gasolinera_id = ? AND activo = 1 AND id != ?
        """, (gasolinera_id, excluir_id))
    else:
        cur.execute("""
            SELECT COALESCE(SUM(litros_reservados), 0) AS total
            FROM subinventarios WHERE gasolinera_id = ? AND activo = 1
        """, (gasolinera_id,))
    suma_otros = float(cur.fetchone()["total"] or 0)
    if suma_otros + litros_propuestos > stock_actual + 0.001:
        raise SubinventarioError(
            f"La reserva total ({suma_otros + litros_propuestos:,.2f} L) superaría el stock "
            f"físico actual ({stock_actual:,.2f} L)."
        )


def crear_subinventario(cur, gasolinera_id, nombre, tipo, cliente_id, litros_iniciales):
    """Crea un subinventario nuevo con el mismo cursor/transacción del llamador.
    Valida el tope de stock físico. Devuelve el id del subinventario creado."""
    validar_tope_reserva(cur, gasolinera_id, litros_iniciales)
    cur.execute("""
        SELECT COALESCE(MAX(orden_prioridad), -1) + 1 AS siguiente
        FROM subinventarios WHERE gasolinera_id = ? AND activo = 1
    """, (gasolinera_id,))
    orden = cur.fetchone()["siguiente"]
    cur.execute("""
        INSERT INTO subinventarios
            (gasolinera_id, nombre, tipo, orden_prioridad, litros_reservados, cliente_id, activo)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (gasolinera_id, nombre, tipo, orden, litros_iniciales, cliente_id or None))
    return cur.lastrowid


def ajustar_reserva(cur, gasolinera_id, subinventario_id, delta_litros):
    """Suma (delta_litros > 0) o resta (delta_litros < 0) litros_reservados de un
    subinventario existente, con el mismo cursor/transacción del llamador.

    Si delta_litros es positivo, valida el tope de stock físico. Si es negativo,
    nunca deja litros_reservados por debajo de 0 (se acota).

    Devuelve (litros_anterior, litros_nuevo) para que el llamador pueda detectar
    si el ajuste se acotó respecto a lo solicitado.
    """
    cur.execute(
        "SELECT litros_reservados FROM subinventarios WHERE id = ? AND gasolinera_id = ?",
        (subinventario_id, gasolinera_id),
    )
    row = cur.fetchone()
    if not row:
        raise SubinventarioError("Subinventario no encontrado.")

    anterior = float(row["litros_reservados"])
    propuesto = anterior + delta_litros
    nuevo = max(propuesto, 0.0)

    if delta_litros > 0:
        validar_tope_reserva(cur, gasolinera_id, nuevo, excluir_id=subinventario_id)

    cur.execute("""
        UPDATE subinventarios SET litros_reservados = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
    """, (nuevo, subinventario_id))
    return anterior, nuevo
