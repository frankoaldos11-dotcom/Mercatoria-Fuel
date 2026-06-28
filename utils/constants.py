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

TIPOS_MOVIMIENTO = [
    "recepcion",
    "transferencia",
    "despacho",
    "ajuste",
    "reasignacion",
    "habilitacion",
]
