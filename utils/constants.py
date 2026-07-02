ROLES = {
    "ADMIN":               "admin",
    "PM":                  "pm",
    "PUESTO_DE_MANDO":     "puesto_de_mando",
    "OPERADOR_GASOLINERA": "operador_gasolinera",
    "SUPERVISOR":          "supervisor",
    "CLIENTE":             "cliente",
}

ROLES_ADMIN_PM = ["admin", "pm"]
ROLES_OPERARIO_GAS = ["admin", "pm", "puesto_de_mando", "operador_gasolinera"]
ROLES_OPERARIO_DEP = ["admin", "pm", "supervisor", "puesto_de_mando"]

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

ESTADOS_HABILITACION = ["pendiente", "aprobada", "despachada", "cancelada", "conciliada"]

ESTADOS_HABILITACION_LABELS = {
    "pendiente":  "Pendiente",
    "aprobada":   "Aprobada",
    "despachada": "Despachada",
    "cancelada":  "Cancelada",
    "conciliada": "Conciliada",
}

ESTADOS_DESPACHO = ["completado", "anulado"]

ESTADOS_CONCILIACION = ["borrador", "cerrada", "con_alerta"]

ESTADOS_LLEGADA_PUERTO = ["en_puerto", "transferido", "anulado"]

ESTADOS_LLEGADA_LABELS = {
    "en_puerto":  "En puerto",
    "transferido": "Transferido",
    "anulado":    "Anulado",
}

TURNOS_CONCILIACION = ["manana", "tarde", "noche"]

TURNOS_CONCILIACION_LABELS = {
    "manana": "Mañana",
    "tarde":  "Tarde",
    "noche":  "Noche",
}
