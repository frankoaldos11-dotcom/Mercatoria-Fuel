# 02 — QA MASTER
# Especificación de verificación con Playwright MCP
# Versión: 1.0 | Estado: APROBADO

Todo sprint se verifica con Playwright MCP antes del commit final. Esta es la especificación de qué verificar en cada sprint de Mercatoria Fuel. Para Mercatoria Trucks aplica el mismo principio con sus propios flujos.

URL de producción: https://mercatoria-fuel.onrender.com
Credenciales de QA: admin@mercatoria.com / Mercatoria2026!

---

## FLUJO BASE (verificar en TODOS los sprints)

1. Navegar a `/` — debe redirigir a `/login` con HTTP 302.
2. Login con credenciales de QA — debe llegar al dashboard con HTTP 200.
3. Verificar que el sidebar muestra todos los módulos esperados.
4. Verificar que el módulo TL38 muestra badge "Próximamente".
5. Logout — debe redirigir a `/login`.

---

## SPRINT 1 — Infraestructura base

- Login y logout funcionales.
- Dashboard carga con las 8 cards en cero.
- CRUD de gasolineras: crear, editar, desactivar.
- Screenshot del dashboard y del listado de gasolineras.

## SPRINT 2 — Clientes, Vehículos, Choferes

- Listado de clientes muestra los 5 clientes del seed.
- Crear un cliente nuevo y verificar que aparece en el listado.
- Detalle del cliente muestra sus unidades (vehículos + choferes).
- Listado de choferes muestra badge de licencia vencida cuando corresponde.
- Dashboard muestra card "Licencias por vencer" con conteo correcto.
- Screenshot del listado de clientes y detalle de un cliente.

## SPRINT 3 — Depósitos, Recepciones, Transferencias

- Crear un depósito y verificar que aparece en el listado con stock 0.
- Crear una recepción y confirmarla — el stock del depósito debe subir.
- Crear una transferencia y confirmar la salida — el stock del depósito debe bajar.
- Confirmar la llegada de la transferencia — el stock de la gasolinera debe subir.
- Dashboard muestra inventario total y combustible en tránsito con datos reales.
- Screenshot del detalle del depósito antes y después de la recepción.

## SPRINT 4 — Tarjetas y Subinventarios

- Listado de tarjetas muestra badges de saldo bajo y devoluciones pendientes.
- Detalle de tarjeta con devolución pendiente muestra saldo usable y retenido por separado.
- Registrar una recarga: el saldo usable sube correctamente.
- Registrar una devolución retenida: los litros pasan de usable a retenido.
- Liberar una devolución: los litros vuelven de retenido a usable.
- Vista de gasolinera muestra sección de subinventarios con disponible para venta.
- Dashboard muestra "Tarjetas con bajo saldo" con conteo real.
- Screenshot del listado de tarjetas y detalle de tarjeta con devolución.

## SPRINT 5 — Habilitaciones, Despachos, Conciliación

- Crear una habilitación: cliente + vehículo + chofer + litros + tarjeta.
- Sistema valida que el vehículo y chofer están activos.
- Sistema valida que la tarjeta tiene saldo usable suficiente.
- Aprobar la habilitación y ejecutar el despacho con foto de ticket.
- Verificar que el saldo de la tarjeta bajó correctamente.
- Verificar que el subinventario del cliente bajó correctamente.
- Crear una conciliación diaria y verificar que muestra diferencias automáticas.
- Screenshot del flujo completo habilitación → despacho → conciliación.

## SPRINT 6 — Portal Cliente, TL38, Reportes

- Login con credenciales de cliente — debe ver solo su portal.
- Portal cliente muestra historial, consumo mensual y sus vehículos.
- Módulo TL38 muestra listado de movimientos independiente de Mercatoria.
- Exportar reporte a Excel y verificar que descarga correctamente.
- Screenshot del portal cliente y del módulo TL38.

---

## PROCEDIMIENTO ESTÁNDAR DE QA

Antes de cada commit de cierre de sprint:

1. Ejecutar el flujo base completo.
2. Ejecutar los flujos específicos del sprint actual.
3. Tomar screenshot de cada pantalla principal verificada.
4. Si se detecta cualquier error: corregirlo antes del commit. Nunca hacer commit con errores conocidos.
5. Incluir en el Resumen de Continuidad el resultado del QA: pantallas verificadas, errores encontrados y corregidos.

---

## ERRORES CRÍTICOS (bloquean el commit)

- Cualquier ruta que devuelva 500.
- Login no funcional.
- Stock que muestra valor incorrecto.
- Saldo de tarjeta que no refleja el último movimiento.
- Formulario que guarda datos sin validación de campos obligatorios.
- Acción que modifica inventario sin insertar en movimientos.
