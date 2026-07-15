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


def apartar_remanente_despacho(cur, hab, litros_despachados, habilitacion_id, despacho_id, responsable_id):
    """Aparta como reserva el remanente (litros_autorizados - litros_despachados) de un
    despacho parcial, con el mismo cursor/transacción del llamador (todo-o-nada con el
    despacho: si esto lanza SubinventarioError, el llamador debe abortar sin commit).

    `hab` debe incluir gasolinera_id, cliente_id, cliente_nombre, litros_autorizados y
    subinventario_id (puede ser None).

    - Si litros_despachados >= litros_autorizados, no hace nada (remanente <= 0).
    - Si la habilitación ya tenía subinventario_id (venía de una reserva), el remanente ya
      quedó reservado ahí: el código de despacho solo decrementa litros_reservados por lo
      efectivamente despachado, nunca por litros_autorizados. No se ajusta ningún número
      acá — solo se deja constancia trazable de que ese remanente viene de un despacho
      parcial y no de la reserva original.
    - Si no tenía subinventario_id, se busca (o crea) el subinventario tipo 'cliente' de
      ese cliente en esa gasolinera y se le suma el remanente con ajustar_reserva().

    En ambos casos registra un movimiento tipo 'remanente_despacho' para trazabilidad.
    """
    litros_autorizados = float(hab["litros_autorizados"])
    remanente = round(litros_autorizados - float(litros_despachados), 6)
    if remanente <= 0.001:
        return

    gasolinera_id = hab["gasolinera_id"]
    cliente_id = hab["cliente_id"]

    if hab["subinventario_id"]:
        sub_id = hab["subinventario_id"]
    else:
        cur.execute("""
            SELECT id FROM subinventarios
            WHERE gasolinera_id = ? AND cliente_id = ? AND tipo = 'cliente' AND activo = 1
            ORDER BY id LIMIT 1
        """, (gasolinera_id, cliente_id))
        existente = cur.fetchone()
        if existente:
            sub_id = existente["id"]
        else:
            sub_id = crear_subinventario(
                cur, gasolinera_id, f"Reserva — {hab['cliente_nombre']}", "cliente", cliente_id, 0
            )
        ajustar_reserva(cur, gasolinera_id, sub_id, remanente)

    despacho_ref = f" / Despacho #{despacho_id}" if despacho_id else ""
    cur.execute("""
        INSERT INTO movimientos
            (tipo, fecha, gasolinera_id, cliente_id, subinventario_destino_id,
             litros, responsable_id, observaciones)
        VALUES ('remanente_despacho', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
    """, (
        gasolinera_id, cliente_id, sub_id, remanente, responsable_id,
        f"Remanente de despacho parcial — Habilitación #{habilitacion_id}{despacho_ref} — "
        f"autorizados {litros_autorizados:,.2f} L, despachados {float(litros_despachados):,.2f} L."
    ))
