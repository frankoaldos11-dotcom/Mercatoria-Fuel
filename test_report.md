# Reporte de Pruebas — 2026-06-28

## Páginas probadas
- http://127.0.0.1:5002/login
- http://127.0.0.1:5002/dashboard
- http://127.0.0.1:5002/habilitaciones
- http://127.0.0.1:5002/habilitaciones/crear
- http://127.0.0.1:5002/habilitaciones/1 (crear → aprobar → verificar estado)
- http://127.0.0.1:5002/unidades (listado vacío detectado)
- http://127.0.0.1:5002/unidades/crear (crear unidad TEST-001 para PMA-001)
- http://127.0.0.1:5002/despachos/crear?habilitacion_id=1
- http://127.0.0.1:5002/despachos/1
- http://127.0.0.1:5002/tarjetas (verificación de saldo)
- http://127.0.0.1:5002/conciliacion/crear (paso 1 + paso 2)
- http://127.0.0.1:5002/conciliacion/1
- http://127.0.0.1:5002/dashboard (verificación final de KPIs)

## Errores encontrados
- **Ninguno.** Todos los flujos completaron sin errores HTTP 4xx/5xx ni excepciones de Python.
- Nota: Puerto 5000 estaba ocupado por otra aplicación Flask ("Mercatoria Truck"). Se inició Mercatoria Fuel en el puerto 5002 usando `python -m flask run --port=5002`.

## Screenshots tomados
- `dashboard.png` — Dashboard inicial post-login con KPIs Sprint 5
- `habilitacion_detalle.png` — Habilitación #1 en estado "Pendiente" antes de aprobar
- `despacho_detalle.png` — Despacho #1 completado con foto de ticket
- `conciliacion_detalle.png` — Conciliación #1 cerrada con diferencia +0.00 L
- `dashboard_final.png` — Dashboard final con despachos_pendientes=0, conciliaciones_pendientes=0

## Flujo completo verificado (Sprint 5)

| Paso | Resultado |
|------|-----------|
| Login admin@mercatoria.com | ✅ Redirige a /dashboard |
| Dashboard carga KPIs sin error | ✅ despachos_pendientes=0, conciliaciones_pendientes=0 |
| /habilitaciones listado carga | ✅ Tabla vacía, sin error |
| /habilitaciones/crear — dropdowns cargan | ✅ clientes, unidades (JS filter), gasolineras, tarjetas, subinventarios |
| Crear unidad TEST-001 para PMA-001 | ✅ Unidad creada con chofer Chofer Prueba, licencia hasta 2027-12-31 |
| Crear habilitación PMA-001 / TEST-001 / La Shell / **** 8777 / 50 L | ✅ Estado: Pendiente |
| Aprobar habilitación #1 | ✅ Estado cambia a: Aprobada |
| /despachos/crear — habilitación aprobada aparece en selector | ✅ Pre-seleccionada con 50.00 L |
| Registrar despacho con foto ticket (upload PNG) | ✅ Despacho #1 creado, redirige a /despachos/1 |
| Habilitación #1 → estado "Despachada" | ✅ Verificado en /habilitaciones/1 |
| Saldo tarjeta **** 8777: 3,300 → 3,250 L (−50 L) | ✅ Verificado en /tarjetas |
| /conciliacion/crear paso 1 → La Shell / 2026-06-28 | ✅ Datos calculados: entrada=0, despachado=50 L |
| Conciliación paso 2: saldo_inicio=3300, saldo_fin=3250 | ✅ diferencia=+0.00 L, estado=Cerrada |
| Dashboard final: despachos_pendientes=0 | ✅ |
| Dashboard final: conciliaciones_pendientes=0 | ✅ |

## Correcciones aplicadas
- Ninguna corrección fue necesaria durante esta sesión. Correcciones previas (campo `t.tarjeta_parcial` → `t.numero_parcial`, filtro Jinja2 `|abs`) ya habían sido aplicadas antes de esta sesión de pruebas.

## Recomendaciones
- El puerto 5000 está ocupado permanentemente por otra aplicación Flask en este equipo ("Mercatoria Truck"). Para desarrollo paralelo, asignar puertos fijos distintos en cada proyecto.
- El inventario total en el dashboard muestra 0 L porque no hay depósitos con stock en la base de datos de desarrollo. Agregar datos de prueba de recepciones para visualizar las KPIs de inventario.
- Considerar validar en el backend que `litros_despachados <= litros_autorizados` para evitar despachos que excedan la autorización.
