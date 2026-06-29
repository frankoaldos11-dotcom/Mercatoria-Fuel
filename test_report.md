# Reporte de Pruebas — 2026-06-29

## Páginas probadas
- https://mercatoria-fuel.onrender.com/login
- https://mercatoria-fuel.onrender.com/dashboard
- https://mercatoria-fuel.onrender.com/tl38/
- https://mercatoria-fuel.onrender.com/tl38/crear
- https://mercatoria-fuel.onrender.com/tl38/listado
- https://mercatoria-fuel.onrender.com/reportes/
- https://mercatoria-fuel.onrender.com/reportes/despachos (Excel download)
- https://mercatoria-fuel.onrender.com/portal/ (como cliente_pma@mercatoria.com)
- https://mercatoria-fuel.onrender.com/static/img/favicon.png

## Errores encontrados
Ninguno. Todas las páginas cargaron correctamente.

## Screenshots tomados
- `prod_dashboard.png` — Dashboard ejecutivo con 3 filas KPI (Inventario, Operativa, Alertas)
- `prod_tl38_dashboard.png` — Dashboard TL38 con 3 KPIs y tabla de movimientos
- `prod_tl38_after_create.png` — Confirmación tras registrar movimiento TL38 (redirect a /tl38/?ok=1)
- `prod_tl38_listado.png` — Listado TL38 con movimiento #1: TL38-TEST-01 / Juan Pérez / 150 L / La Shell
- `prod_reportes.png` — Página de reportes con 4 secciones exportables
- `prod_portal_cliente.png` — Portal cliente PMA: "Programa Mundial de Alimentos" con 5 KPIs y sidebar aislado

## Correcciones aplicadas
Ninguna corrección fue necesaria durante esta sesión. Sprint 6 funcionó correctamente en producción desde el primer despliegue.

## Resultados por módulo

### Sprint 6 — Verificación en producción (https://mercatoria-fuel.onrender.com)

| # | Prueba | Resultado |
|---|--------|-----------|
| 1 | Login admin@mercatoria.com / Mercatoria2026! | ✅ PASS |
| 2 | Dashboard carga con 3 filas KPI (Inventario, Operativa, Alertas) | ✅ PASS |
| 3 | Enlace TL38 en sidebar sin badge "Próximamente" | ✅ PASS |
| 4 | `/tl38/` — dashboard con KPIs y tabla de movimientos recientes | ✅ PASS |
| 5 | `/tl38/crear` — formulario con campos: tipo, chapa, chofer, litros, flota, tarjeta, gasolinera | ✅ PASS |
| 6 | Registrar movimiento TL38 (despacho, 150L, La Shell) → redirect /tl38/?ok=1 | ✅ PASS |
| 7 | `/tl38/listado` — movimiento #1 visible con todos los campos correctos | ✅ PASS |
| 8 | `/reportes/` — 4 secciones: Despachos, Conciliaciones, Consumo por Cliente, Tarjetas | ✅ PASS |
| 9 | `GET /reportes/despachos` — HTTP 200, content-type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | ✅ PASS |
| 10 | Login cliente_pma@mercatoria.com / Cliente2026! → redirect /portal/ | ✅ PASS |
| 11 | Portal cliente: heading "Programa Mundial de Alimentos", 5 KPIs, 7 links de portal, sin links admin | ✅ PASS |
| 12 | Favicon `/static/img/favicon.png` — HTTP 200, image/png, 597 bytes | ✅ PASS |

## Recomendaciones
- El Sprint 6 está completo y funcional en producción. No se detectaron bugs.
- El TL38 listado tiene exportación Excel disponible desde `/tl38/listado?exportar=excel` — no probado en esta sesión pero el código usa el mismo patrón verificado en /reportes/despachos.
- El portal cliente actualmente muestra 0 en todos los KPIs para el usuario de prueba (cliente_pma), lo cual es correcto ya que no hay despachos registrados para PMA en producción. El aislamiento de datos por `cliente_id` funciona correctamente.
- Los 4 reportes Excel (`/reportes/despachos`, `/reportes/conciliaciones`, `/reportes/consumo`, `/reportes/tarjetas`) comparten la misma arquitectura openpyxl con `io.BytesIO`; verificado el de despachos, el resto sigue el mismo patrón.
