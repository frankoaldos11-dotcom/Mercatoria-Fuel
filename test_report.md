# Reporte de Pruebas — 2026-06-29

## Páginas probadas

- http://127.0.0.1:5000/login
- http://127.0.0.1:5000/dashboard
- http://127.0.0.1:5000/tarjetas/
- http://127.0.0.1:5000/tarjetas/1
- http://127.0.0.1:5000/tarjetas/1/recargar
- http://127.0.0.1:5000/tarjetas/1/devolucion
- http://127.0.0.1:5000/tarjetas/1 (liberación POST desde tabla)
- http://127.0.0.1:5000/gasolineras/1
- http://127.0.0.1:5000/gasolineras/1/subinventarios/crear
- http://127.0.0.1:5000/gasolineras/1/subinventarios/1/editar
- http://127.0.0.1:5000/gasolineras/1 (toggle POST subinventario)
- http://127.0.0.1:5000/gasolineras/1/reasignar

## Errores encontrados

- **Ninguno.** Solo se detectó un HTTP 404 en `/favicon.ico`, que es esperado (sin favicon configurado). Sin errores de consola JS ni excepciones del servidor.

## Screenshots tomados

- Ninguno capturado explícitamente. Snapshots de accesibilidad registrados en `.playwright-mcp/`.

## Correcciones aplicadas

- Ninguna. Todos los flujos pasaron sin requerir correcciones.

## Resultados detallados (Sprint 4)

### Tarjetas Fincimex

| Ruta | Resultado | Observación |
|------|-----------|-------------|
| `GET /tarjetas/` | ✅ PASS | 5 tarjetas listadas con saldos usable/retenido correctos, filtros funcionales |
| `GET /tarjetas/1` | ✅ PASS | Detalle muestra saldo usable 3,200 L, retenido 0 L, estado Activa, secciones Recargas y Devoluciones |
| `POST /tarjetas/1/recargar` | ✅ PASS | +100 L → saldo 3,200 → 3,300 L. Mensaje "Operación realizada con éxito." |
| `POST /tarjetas/1/devolucion` | ✅ PASS | Retención 50 L → usable 3,300 → 3,250 L, retenido 0 → 50 L. Slips registrados. |
| `POST liberar_devolucion` | ✅ PASS | Confirmar dialog → retenido 50 → 0 L, usable 3,250 → 3,300 L. Estado dev. = liberada. |

### Subinventarios en Gasolineras

| Ruta | Resultado | Observación |
|------|-----------|-------------|
| `GET /gasolineras/1/subinventarios/crear` | ✅ PASS | Formulario carga con campos nombre, tipo, orden, litros |
| Validación stock (500 L > 0 L) | ✅ PASS | Rechaza correctamente: "La reserva total (500.00 L) superaría el stock físico actual (0.00 L)." |
| `POST crear` (0 L) | ✅ PASS | Subinventario "Reserva QA Sprint4" creado, redirige a `/gasolineras/1?ok=1` |
| `GET /gasolineras/1/subinventarios/1/editar` | ✅ PASS | Carga con valores pre-rellenos del registro |
| `POST editar` (cambio de nombre) | ✅ PASS | Nombre actualizado a "Reserva QA Sprint4 (editado)", redirige con `?ok=1` |
| `POST toggle` (Activo → Inactivo) | ✅ PASS | Confirmar dialog → estado cambia a Inactivo en tabla |
| `GET /gasolineras/1/reasignar` | ✅ PASS | Página carga con formulario de origen/destino/litros. Selectores vacíos (correcto: subinventario inactivo) |

## Recomendaciones

- **Favicon:** Añadir `static/favicon.ico` para eliminar el 404 en consola de todos los usuarios.
- **Reasignar con datos reales:** La ruta `/reasignar` no pudo probarse end-to-end porque el único subinventario del entorno de prueba estaba inactivo. Pendiente verificar en un entorno con ≥2 subinventarios activos y stock > 0.
- **Tarjetas 0898 y 0880:** Tienen devoluciones pendientes seeded (seed de migraciones). Verificar que el dashboard muestra la alerta `alertas_criticas` cuando `fecha_estimada_liberacion <= hoy`.
- **Test en producción:** El seed de Render incluye 5 tarjetas diesel y 2 devoluciones pendientes — QA en producción cubriría el caso de reasignación con datos reales.
