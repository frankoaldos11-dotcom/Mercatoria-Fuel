# Reporte de Pruebas — 2026-07-05

## Páginas probadas

| URL | Título | Resultado |
|-----|--------|-----------|
| `/login` | Iniciar Sesión | ✅ |
| `/dashboard` | Dashboard | ✅ |
| `/transferencias/` | Transferencias — listado | ✅ |
| `/gasolineras/` | Gasolineras — listado | ✅ |
| `/gasolineras/1` | La Shell — detalle | ✅ |
| `/gasolineras/2` | Berroa — detalle | ✅ |
| `/tarjetas/` | Tarjetas Fincimex | ✅ |
| `/tarjetas/1` | Tarjeta ****8777 — detalle (botón Editar) | ✅ |
| `/tarjetas/1/editar` | Editar Tarjeta ****8777 | ✅ |
| `/tienda/reservar` | Nueva reserva (sin vehículo) | ✅ bloqueado |
| `/tienda/reservar` | Nueva reserva (con vehículo ABC-001) | ✅ permitido |
| `/tienda/admin` | Panel reservas — aprobar #4 | ✅ |
| `/despachos/` | Despachos — reserva aprobada visible | ✅ |

## Errores encontrados

| Tipo | Descripción | Estado |
|------|-------------|--------|
| 500 Server Error | `/gasolineras/1` — TypeError en `fecha_despacho[:16]` (PostgreSQL) | ✅ Corregido commit `8e8293a` |
| Bug lógico | Reserva creable sin vehículo — `vehiculo_id` no validado en backend | ✅ Corregido commit `82d6a9c` |
| Bug lógico | Reserva aprobada invisible en flujo de despacho | ✅ Corregido commit `82d6a9c` |
| 0 errores JS consola | Sin errores en ninguna página verificada | ✅ |

## Screenshots tomados

- `sprint8_i1i2ci5_transferencias_listado.png` — Listado de transferencias (Sprint 8)
- `sprint8_i3i4_gasolinera_detalle.png` — La Shell detalle (Sprint 8)
- `sprint8_i4_gasolinera_berroa_detalle.png` — Berroa detalle (Sprint 8)
- `sprint8_tarjeta_editar_form.png` — Formulario editar tarjeta
- `sprint8_tarjeta_editar_aviso_saldo.png` — Aviso JS de saldo al cambiar gasolinera
- `sprint8_tarjeta_editar_guardado_ok.png` — Detalle tras guardar tarjeta
- `sprint8_tarjeta_editar_listado_final.png` — Listado de tarjetas final
- `tienda_bug1_sin_vehiculo_bloqueado.png` — Formulario bloqueado sin vehículos: aviso + enlace, sin botón submit
- `tienda_bug1_reserva_con_vehiculo_ok.png` — Reserva #4 confirmada con vehículo ABC-001 Toyota Hilux
- `tienda_bug2_reserva_aprobada_en_despachos.png` — Reserva #4 aprobada visible en /despachos con botón Escanear QR

## Correcciones aplicadas

### Sprint 8 — Issues 1-5 (commits `e8089ef`, `8e8293a`)
Ver historial anterior. Todos verificados en producción.

### Reasignación de gasolinera en tarjeta Fincimex (commit `4b74c9a`)
Verificado: La Shell → Berroa → La Shell, saldo 3,200 L intacto en todo momento.

### Bug 1 — Vehículo obligatorio en reserva de tienda (commit `82d6a9c`)

**Causa:** backend no validaba `vehiculo_id`; tabla `reservas_tienda` sin FK a `vehiculos_tienda`.

**Correcciones:**
- `migraciones_pg.py` / `migraciones.py`: `ALTER TABLE reservas_tienda ADD COLUMN IF NOT EXISTS vehiculo_id INTEGER REFERENCES vehiculos_tienda(id)`
- `blueprints/tienda.py` POST `/reservar`: sin vehículos → error inmediato; `vehiculo_id` vacío o ajeno al cliente → error; `vehiculo_id` guardado en INSERT
- `templates/tienda/reservar.html`: sin vehículos → aviso bloqueante + enlace, formulario oculto; con vehículos → `<select required>` sin opción "Otro vehículo"

| Prueba | Resultado |
|--------|-----------|
| Sin vehículos → `/tienda/reservar` | ✅ Formulario oculto, mensaje "Debes registrar al menos un vehículo", enlace a mis-vehículos |
| Con vehículo ABC-001 Toyota Hilux → 500 L La Shell Diésel | ✅ Reserva #4 creada, redirección a confirmación |

### Bug 2 — Reserva aprobada visible en Despachos (commit `82d6a9c`)

**Causa:** `reservas_tienda` era tabla aislada; `/despachos` nunca consultaba reservas de tienda.

**Correcciones:**
- `blueprints/despachos.py` `listado()`: segunda query `reservas_tienda WHERE estado='aprobada'`. `operador_gasolinera` → solo su gasolinera; admin/pm/puesto_de_mando → todas.
- `templates/despachos/listado.html`: sección "Reservas de Tienda — Pendientes de despachar" encima de la tabla principal, con botón "Escanear QR" → `/turno/escanear`

**Reglas respetadas:** `api_reserva_completar` (turno.py) sigue siendo el único punto de completado. Descuenta de `saldo_usable_l`. Idempotente (segundo escaneo rechazado si `estado != 'aprobada'`).

| Prueba | Resultado |
|--------|-----------|
| Aprobar reserva #4 vía `/tienda/admin` | ✅ `{"ok": true, "token": "61c9b1cc-..."}` |
| `/despachos/` tras aprobación | ✅ Sección naranja "Reservas de Tienda", Cliente PMA, ABC-001, 500.00 L, botón Escanear QR |

## Commits del sprint

| Hash | Mensaje |
|------|---------|
| `82d6a9c` | Tienda: vehiculo obligatorio en reserva + reserva aprobada visible en Despachos para escaneo |
| `5eaec61` | MDS: integrar lecciones sesion estabilizacion PostgreSQL |
| `4b74c9a` | Permitir reasignar gasolinera de tarjeta Fincimex con aviso de saldo + auditoria |
| `be4cd4a` | Sprint 8: test_report.md QA Playwright — 5 issues verificados en produccion |
| `8e8293a` | fix: filtro \|string en fecha_despacho para compatibilidad SQLite/PostgreSQL |

## Recomendaciones

- **DEUDA ABIERTA — saldo inicial de tarjeta**: tecleado a mano al crear, permite introducir saldo sin flujo real. Evaluar forzar `saldo_usable_l = 0` al crear y exigir primera recarga vía flujo.
- **Backfill de litros_distribuidos**: transferencias históricas tienen 0 aunque ya distribuyeron. Aplicar UPDATE basado en movimientos si se necesita trazabilidad retroactiva.
- **Migración PostgreSQL free tier**: expira 2026-07-26. Migrar antes de esa fecha.
- **Auditoría de reasignaciones de tarjeta**: registradas en tabla `auditoria`. Considerar vista en panel admin si se necesita trazabilidad visible.
