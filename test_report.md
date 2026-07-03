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

### Verificación adicional tienda/admin y choferes/editar

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| V1 | `/tienda/admin` carga sin 500 | ✅ PASS | Panel de reservas renderiza sin error; tabla vacía (sin reservas aún) |
| V2 | `/choferes/1/editar` carga sin 500 | ✅ PASS | Formulario editar chofer renderiza correctamente |
| V2 | `licencia_vencimiento` muestra `2027-06-30` en el `<input type="date">` | ✅ PASS | Objeto `date` de PostgreSQL formateado sin error por `(valor \| string)[:10]` |
| V2 | Consola sin errores JS | ✅ PASS | 0 errores en consola en ambas páginas |

Chofer de prueba creado durante la verificación: "Chofer Prueba PG", CI 99999999999, cliente PMA-001, licencia LIC-TEST-001, vence 2027-06-30.

## Recomendaciones pendientes
1. **Crear cuenta operador_gasolinera de prueba** y verificar que el sidebar muestra solo "Operador Gasolinera" y que turno fuerza su gasolinera asignada.
2. **Crear cuenta puesto_de_mando de prueba** y verificar acceso a Puertos + Operativa pero no a Comercial/Sistema.
3. **Verificar `/tienda/qr_vista`** (QR de reserva) con una reserva real aprobada cuando haya datos de `reservas_tienda`.

---

# Reporte de Pruebas — 2026-07-02 (continuación)

## Commits verificados
- `74332e2` — Validacion suma exacta litros distribucion + logging de excepciones en handler 500
- `d21aef3` — Fix float/Decimal en gasolineras detalle + barrido de operaciones aritméticas mixtas

## Páginas probadas
- https://mercatoria-fuel.onrender.com/gasolineras/1
- https://mercatoria-fuel.onrender.com/gasolineras/
- https://mercatoria-fuel.onrender.com/transferencias/2/gestionar

## Resultados por verificación

### commit 74332e2 — B2 Validación suma exacta + D1 Logging 500

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| B2-1 | `/transferencias/2/gestionar` carga en estado "recibida" con form de distribución | ✅ PASS | Paso 3 visible con texto actualizado |
| B2-2 | Texto describe suma exacta (ya no dice "parcialmente") | ✅ PASS | "La suma de todos los campos debe igualar **exactamente** ese total." |
| B2-3 | Panel "Suma asignada" muestra 0.00 L al inicio | ✅ PASS | Panel izquierdo reactivo |
| B2-4 | Panel "Total requerido" muestra 500.00 L | ✅ PASS | Dato de transferencia #2 |
| B2-5 | Botón "Asignar a tarjetas" deshabilitado al inicio | ✅ PASS | `[disabled]` confirmado en snapshot |
| B2-6 | Al ingresar 300 L en tarjeta 0880 → "Faltan 200,00 L por asignar" | ✅ PASS | Contador live actualiza en tiempo real |
| B2-7 | Al completar 300+200=500 L → "✓ Suma exacta — listo para asignar." | ✅ PASS | Mensaje verde, botón se habilita |
| B2-8 | Botón se habilita solo cuando suma == 500.00 exacto | ✅ PASS | `[cursor=pointer]` confirmado (ya no `[disabled]`) |
| D1 | Handler 500 con traceback logging en `app.py` | ✅ PASS | Logging permanente añadido; traceback se escribe en Render logs |

### commit d21aef3 — Fix float/Decimal TypeError en `/gasolineras/<id>`

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| F1 | `stock_total = float(sum(...))` — siempre float | ✅ PASS | Evita `sum([]) = int(0)` mezclado con Decimal |
| F2 | `/gasolineras/1` carga sin 500 | ✅ PASS | Antes: `float / Decimal('50000')` → TypeError. Ahora OK |
| F3 | KPI de stock y barra de porcentaje renderiza correctamente | ✅ PASS | 12.499,00 L de stock total visible |
| F4 | Subinventarios con `(s.litros_reservados \| float)` sin error | ✅ PASS | Tabla de subinventarios carga |
| F5 | 0 errores de consola JS | ✅ PASS | |
| Barrido | `dashboard.html:201` — `Decimal / Decimal * int` | ✅ SEGURO | Sin riesgo |
| Barrido | `transferencias/listado.html:95` — `Decimal / Decimal * int` | ✅ SEGURO | Sin riesgo |
| Barrido | `recepciones/listado.html:97` — `Decimal / Decimal * int` | ✅ SEGURO | Sin riesgo |
| Barrido | `portal/consumo_vehiculo.html:30` — `Decimal / int` | ✅ SEGURO | Sin riesgo |

## Errores encontrados
Ninguno — todos los errores anteriores corregidos en estos commits.

## Screenshots tomados
- `gasolineras_fix_01_detalle_La_Shell.png` — `/gasolineras/1` cargando correctamente post-fix
- `gasolineras_fix_02_listado.png` — Listado de gasolineras
- `b2_01_distribuir_inicial.png` — Formulario distribución con suma 0.00 L y botón disabled
- `b2_02_distribuir_exacto.png` — Formulario con suma exacta 500.00 L y botón habilitado

## Correcciones aplicadas

### Bug /gasolineras/1 — TypeError float/Decimal (commit d21aef3)
Root cause: `stock_total` era `float` cuando había movimientos (convertido via `float(r["stock"])`), pero `gasolinera.capacidad_l` llegaba como `decimal.Decimal` desde psycopg2. `float / Decimal` → TypeError en Python 3. En DB vacía `sum([]) = int(0)` y `int / Decimal` funciona, enmascarando el bug.

3 fixes aplicados:
- `blueprints/gasolineras.py:129` — `stock_total = float(sum(...))` (siempre float)
- `templates/gasolineras/detalle.html:43` — `(gasolinera.capacidad_l | float)` en divisor
- `templates/gasolineras/detalle.html:135` — `(s.litros_reservados | float)` en dividendo

### B2 — Validación suma exacta distribución (commit 74332e2)
- `blueprints/transferencias.py` → rechaza POST si `abs(suma - litros_recibidos) > 0.005`
- `templates/transferencias/gestionar.html` → contador live, texto actualizado, botón disabled hasta suma exacta
- `app.py` → traceback logging permanente en handler 500

## Recomendaciones pendientes
1. **Crear cuenta operador_gasolinera de prueba** y verificar sidebar y turno con gasolinera asignada.
2. **Crear cuenta puesto_de_mando de prueba** y verificar acceso diferenciado.
3. **Verificar `/tienda/qr_vista`** con una reserva real aprobada.

---

# Reporte de Pruebas — 2026-07-03

## Commits verificados
- `fdfc67a` — Fix seguridad cruce de roles en sesion + 500s latentes PostgreSQL + limpieza roles legacy + mover Tienda a Operaciones
- `644dcc8` — Fix tl38: SUBSTR(CAST(fecha AS TEXT), 1, 7) para compat PostgreSQL DATE
- `d0447a8` — Fix usuarios: INSERT OR IGNORE → INSERT simple (compat PostgreSQL)
- `b9e65bd` — Fix usuarios: INSERT OR IGNORE en crear + int(cliente_id) para compat PostgreSQL FK INTEGER

## Páginas probadas
- https://mercatoria-fuel.onrender.com/login (como admin y como cliente)
- https://mercatoria-fuel.onrender.com/despachos/ (listado)
- https://mercatoria-fuel.onrender.com/despachos/1?ok=1 (detalle)
- https://mercatoria-fuel.onrender.com/tl38/
- https://mercatoria-fuel.onrender.com/tienda/mis-reservas
- https://mercatoria-fuel.onrender.com/usuarios/crear (dropdown roles)
- https://mercatoria-fuel.onrender.com/gasolineras/ (intento cliente)
- https://mercatoria-fuel.onrender.com/clientes/ (intento cliente)
- https://mercatoria-fuel.onrender.com/depositos/ (intento cliente)
- https://mercatoria-fuel.onrender.com/habilitaciones/ (intento cliente)
- https://mercatoria-fuel.onrender.com/dashboard (intento cliente)

## Resultados por verificación

### S1 + S2 — Seguridad: session.clear() + requiere_staff()

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| S1 | `session.clear()` en login antes de setear nueva sesión | ✅ PASS | Stale keys (cliente_id, gasolinera_id) de sesión anterior ya no persisten |
| S2-1 | Cliente → `/gasolineras/` redirige a `/tienda/` | ✅ PASS | `requiere_staff()` activo |
| S2-2 | Cliente → `/clientes/` redirige a `/tienda/` | ✅ PASS | |
| S2-3 | Cliente → `/depositos/` redirige a `/tienda/` | ✅ PASS | |
| S2-4 | Cliente → `/habilitaciones/` redirige a `/tienda/` | ✅ PASS | |
| S2-5 | Cliente → `/despachos/` redirige a `/tienda/` | ✅ PASS | |
| S2-6 | Cliente → `/dashboard` redirige a `/tienda/` | ✅ PASS | Ya existía en dashboard_bp |

### D1-D3 — Fixes 500 PostgreSQL datetime/strftime

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| D1-a | `/despachos/` carga sin 500 | ✅ PASS | `(d.fecha_despacho \| string)[:16]` en listado.html |
| D1-b | `/despachos/1?ok=1` carga sin 500 | ✅ PASS | `(despacho.fecha_despacho \| string)[:16]` en detalle.html |
| D2 | `/tienda/mis-reservas` carga sin 500 | ✅ PASS | `(r.created_at \| string)[:16]` en mis_reservas.html |
| D3 | `/tl38/` carga sin 500 | ✅ PASS | `SUBSTR(CAST(fecha AS TEXT), 1, 7)` — `fecha DATE` requería cast explícito |

### R1 — Roles dropdown (4 opciones)

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| R1 | `/usuarios/crear` muestra exactamente 4 roles | ✅ PASS | Admin, Puesto de Mando, Operador Gasolinera, Cliente |
| R4 | pm/supervisor siguen aceptados como legacy en backend | ✅ PASS | `_ROLES_VALIDOS` incluye pm/supervisor; no se muestran en dropdown |

### T1 — Tienda bajo Operaciones

| # | Verificación | Resultado | Notas |
|---|-------------|-----------|-------|
| T1 | "Tienda" aparece bajo sección "Operaciones" en sidebar | ✅ PASS | Aparece después de Gasolineras, antes de "Comercial" |
| T1 | Badge de reservas pendientes conservado | ✅ PASS | Badge "1" visible en sidebar |
| T1 | Usuarios y Configuración se mantienen bajo "Sistema" | ✅ PASS | |

## Bugs colaterales encontrados y corregidos

### Usuarios crear/editar — compat PostgreSQL
- `INSERT OR IGNORE INTO cliente_usuarios` → SQLite-only. Fix: `INSERT INTO` (se hace DELETE previo en editar; usuario nuevo en crear no tiene conflicto)
- `cliente_id` pasado como `str` al INSERT de FK INTEGER → `int(cliente_id)` explícito para evitar type mismatch en psycopg2

## Errores encontrados
- Console errors en `/despachos/1?ok=1`: 2 errores JS (404 favicon, recurso menor) — no relacionados con los fixes

## Screenshots tomados
- `security_01_cliente_tienda_bloqueado.png` — Cliente logueado, portal tienda (después de intentar /dashboard)
- `security_02_mis_reservas_ok.png` — /tienda/mis-reservas cargando sin 500
- `security_03_despacho_detalle_ok.png` — /despachos/1?ok=1 cargando sin 500
- `security_04_tl38_ok.png` — /tl38/ cargando sin 500
- `security_05_roles_4_opciones.png` — Dropdown con 4 roles exactos

## Correcciones aplicadas

### Commit fdfc67a — Seguridad + 500s + roles + sidebar
- `app.py`: `session.clear()` antes de setear sesión en login
- `utils/auth.py`: `requiere_staff()` — bloquea `rol='cliente'` en rutas operativas
- `blueprints/gasolineras.py`, `clientes.py`, `depositos.py`, `habilitaciones.py`, `despachos.py`: `requiere_staff()` en listado + detalle + crear (despachos)
- `templates/despachos/detalle.html`, `listado.html`, `habilitaciones/detalle.html`, `conciliacion/detalle.html`, `tienda/mis_reservas.html`: `(campo | string)[:16]` en lugar de `campo[:16]`
- `blueprints/tl38.py`: `SUBSTR(fecha, 1, 7)` → `SUBSTR(CAST(fecha AS TEXT), 1, 7)` (fecha es DATE en PG)
- `blueprints/usuarios.py`: `_ROLES_LISTA` = 4 roles; `_ROLES_VALIDOS` incluye pm/supervisor legacy
- `templates/base.html`: Tienda movida a sección Operaciones

### Commits 644dcc8, d0447a8, b9e65bd — Fixes colaterales PG
- Fix TL38 CAST(fecha AS TEXT): DATE no es subscriptable en PostgreSQL
- Fix usuarios INSERT OR IGNORE → INSERT simple (compat PostgreSQL)
- Fix int(cliente_id) para FK INTEGER en psycopg2

## Recomendaciones pendientes
1. **Verificar `/habilitaciones/<id>` y `/conciliacion/<id>`** — fixes D1 latentes aplicados pero no verificados con datos reales (requieren registros existentes).
2. **Crear cuenta operador_gasolinera** y verificar que turno fuerza su gasolinera asignada.
3. **Verificar `/tienda/qr_vista`** con reserva aprobada.
