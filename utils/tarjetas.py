import math

_FACTOR_DEFAULT = 0.90


def obtener_factor(cur):
    """Único punto de lectura del factor_litro_usd — antes duplicado en cada blueprint."""
    cur.execute("SELECT valor FROM configuracion WHERE clave = 'factor_litro_usd'")
    row = cur.fetchone()
    return float(row["valor"]) if row else _FACTOR_DEFAULT


def calcular_usd_desde_litros(litros, factor):
    """USD equivalente a mostrar (o a guardar como espejo) desde una cantidad de
    litros. Redondeo normal a 2 decimales — es una lectura derivada, no crea saldo."""
    return round(float(litros or 0) * float(factor or 0), 2)


def litros_desde_usd_piso(monto_usd, factor):
    """Litros a ACREDITAR a partir de un monto en USD (p.ej. asignar desde el
    bolsón). Redondeo hacia ABAJO a 2 decimales: nunca acredita más litros de
    los que el monto realmente cubre, para que el bolsón no quede descuadrado
    a favor de la tarjeta."""
    if not factor:
        return 0.0
    litros_exactos = float(monto_usd or 0) / float(factor)
    return math.floor(litros_exactos * 100) / 100
