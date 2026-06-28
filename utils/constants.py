ROLES = {
    "ADMIN":      "admin",
    "PM":         "pm",
    "OPERARIO":   "operario",
    "SUPERVISOR": "supervisor",
    "CLIENTE":    "cliente",
}

ROLES_ADMIN_PM = ["admin", "pm"]

REGIONES = ["Occidente", "Centro", "Oriente"]

TIPOS_COMBUSTIBLE = ["diesel", "gasolina_regular", "gasolina_especial"]

TIPOS_COMBUSTIBLE_LABELS = {
    "diesel":            "Diésel",
    "gasolina_regular":  "Gasolina Regular",
    "gasolina_especial": "Gasolina Especial",
}

TIPOS_CLIENTE = ["internacional", "nacional", "interno"]

TIPOS_CLIENTE_LABELS = {
    "internacional": "Internacional",
    "nacional":      "Nacional",
    "interno":       "Interno",
}

TIPOS_SUBINVENTARIO = [
    "cliente",
    "mercatoria_interna",
    "reserva_general",
    "venta",
]

TIPOS_SUBINVENTARIO_LABELS = {
    "cliente":            "Cliente",
    "mercatoria_interna": "Mercatoria Interna",
    "reserva_general":    "Reserva General",
    "venta":              "Venta",
}

ESTADOS_TARJETA = ["activa", "inactiva", "bloqueada"]

ESTADOS_TARJETA_LABELS = {
    "activa":    "Activa",
    "inactiva":  "Inactiva",
    "bloqueada": "Bloqueada",
}

TIPOS_MOVIMIENTO = [
    "recepcion",
    "transferencia_salida",
    "transferencia_entrada",
    "transferencia_anulacion",
    "recarga_tarjeta",
    "despacho",
    "ajuste",
    "reasignacion",
    "habilitacion",
]

ESTADOS_RECEPCION = ["pendiente", "confirmada", "anulada"]

ESTADOS_TRANSFERENCIA = ["en_transito", "recibida", "anulada"]
