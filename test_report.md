# Reporte de Pruebas — 2026-07-02

## Commits verificados
- `390a57d` — Sprint 5: C1–C6 correcciones Tienda
- `566160e` — fix: expose toggleOtroVehiculo globally in tienda/reservar
- `3b4deb8` — Roles: puesto_de_mando y operador_gasolinera con gasolinera asignada, sidebar por puesto
- `6c219e9` — Fix migraciones_pg: reorden esquema antes de seeds + bloque reset temporal guardado por RESET_SCHEMA
- `033427c` — Retira bloque de reset temporal de migraciones_pg tras reconstruccion exitosa de la base
- `0f7a8c9` — Fix fechas: reemplazar slicing [:10] por formato seguro datetime en templates (compat PostgreSQL)

## Páginas probadas
- https://mercatoria-fuel.onrender.com/login
- https://mercatoria-fuel.onrender.com/dashboard
- https://mercatoria-fuel.onrender.com/usuarios/
- https://mercatoria-fuel.onrender.com/usuarios/crear
- https://mercatoria-fuel.onrender.com/turno/?gasolinera_id=1&fecha=2026-07-02
- https://mercatoria-fuel.onrender.com/puertos/
- https://mercatoria-fuel.onrender.com/static/css/admin.css
- https://mercatoria-fuel.onrender.com/unidades/
- https://mercatoria-fuel.onrender.com/clientes/1

## Resultados por verificación

### commit 3b4deb8 — Roles Sprint 5

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| C1 | CSS tipografía: `.nav-section` 13px < `.nav-item` 15px | ✅ PASS | Jerarquía correcta |
| C2 | Roles en formulario crear usuario: sin roles viejos | ✅ PASS | Lista: admin, pm, puesto_de_mando, operador_gasolinera, supervisor, cliente |
| C3 | Dropdown gasolinera aparece al seleccionar `operador_gasolinera` | ✅ PASS | `bloque-gasolinera` visible; "La Shell" cargada desde DB |
| C3 | Dropdown cliente aparece solo al seleccionar `cliente` | ✅ PASS | |
| C4 | Turno page — admin ve selector de gasolinera | ✅ PASS | `<select name="gasolinera_id">` presente |
| C5 | Backend API `/turno/api/:id/despachar` responde JSON | ✅ PASS | `{"error": "Habilitación no encontrada"}` |
| C6 | Puertos — admin ve botón "Registrar llegada" | ✅ PASS | Guard actualizado a `puesto_de_mando` |
| C6 | Admin sidebar: todas las secciones presentes | ✅ PASS | |

### commit 0f7a8c9 — Fix fechas datetime PG

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| F1 | `/usuarios/` carga sin 500 | ✅ PASS | Antes: `TypeError: 'datetime.datetime' object is not subscriptable` en `u.created_at[:10]` |
| F2 | Columna "Creado" muestra fechas con formato `YYYY-MM-DD` | ✅ PASS | Patrón `(valor \| string)[:10]` funciona con objetos datetime de PG |
| F3 | `/unidades/` carga sin 500 | ✅ PASS | `choferes/listado.html` — `licencia_vencimiento` corregido |
| F4 | `/clientes/1` carga sin 500 | ✅ PASS | `clientes/detalle.html` ×2 ocurrencias corregidas |

## Errores encontrados

### No críticos / esperados
- `503` en cold start de Render al inicio de sesión — transitorios, no recurrentes
- `404 /favicon.ico` — conocido desde sesiones anteriores
- `400/404 /turno/api/9999/despachar` — llamadas de prueba de sesión anterior (esperado)

### Stale (sesiones anteriores — ya corregidos)
- `ReferenceError: toggleOtroVehiculo is not defined` — de sesión Playwright previa en `/tienda/reservar`. Fix ya aplicado en commit `566160e`.

## Screenshots tomados

### Sprint 5 — Roles
- `roles_v1_dashboard_admin.png` — Dashboard admin tras login
- `roles_v2_crear_usuario_operador_gasolinera.png` — Formulario crear usuario con gasolinera dropdown
- `roles_v3_usuarios_listado.png` — Listado usuarios con nuevos badges de rol
- `roles_v4_turno_admin.png` — Turno del día admin con selector gasolinera
- `roles_v5_puertos_listado.png` — Puertos listado con botón Registrar llegada visible

### Fix fechas datetime PG
- `fix_fechas_01_usuarios_listado.png` — /usuarios/ cargando correctamente sin 500
- `fix_fechas_02_unidades_listado.png` — /unidades/ cargando sin error (licencia_vencimiento fix)
- `fix_fechas_03_clientes_detalle.png` — /clientes/1 cargando sin error

## Correcciones aplicadas

### migraciones_pg.py (commits 6c219e9, 033427c)
- Reorden completo: todos los CREATE TABLE en orden de dependencias → ALTER TABLE → commit → seeds → commit
- `gasolinera_id` incluido directamente en `CREATE TABLE usuarios`
- Bloque temporal `RESET_SCHEMA=true` aplicado en producción y luego eliminado del código

### Fix fechas (commit 0f7a8c9)
7 ocurrencias de `campo[:10]` sobre objetos `datetime`/`date` de PostgreSQL corregidas
con patrón `(campo | string)[:10]` en 5 templates:

| Template | Campo | Ocurrencias |
|---|---|---|
| `usuarios/listado.html` | `created_at` | 1 |
| `tienda/qr_vista.html` | `created_at` | 1 |
| `tienda/admin.html` | `created_at` | 1 |
| `choferes/listado.html` | `licencia_vencimiento` | 1 |
| `choferes/editar.html` | `licencia_vencimiento` | 1 |
| `clientes/detalle.html` | `licencia_vencimiento` | 2 |

## Recomendaciones pendientes
1. **Verificar `/tienda/admin`** (reservas_tienda) y **`/tienda/qr_vista`** (QR de reserva) en producción cuando haya datos reales de `reservas_tienda` — el fix se aplicó pero no se pudo navegar a una reserva real para confirmar visualmente.
2. **Verificar `/choferes/editar/:id`** con un chofer que tenga `licencia_vencimiento` — confirmar que el campo `<input type="date">` recibe el valor `YYYY-MM-DD` correctamente.
3. **Crear cuenta operador_gasolinera de prueba** y verificar que el sidebar muestra solo "Operador Gasolinera" y que turno fuerza su gasolinera asignada.
4. **Crear cuenta puesto_de_mando de prueba** y verificar acceso a Puertos + Operativa pero no a Comercial/Sistema.
