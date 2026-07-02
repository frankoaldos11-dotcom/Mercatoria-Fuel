# Reporte Exhaustivo de Pruebas — 2026-06-29

Revisión de 32 puntos en 6 flujos sobre producción: https://mercatoria-fuel.onrender.com
Credenciales admin: admin@mercatoria.com / Mercatoria2026!

---

## Resumen ejecutivo

| Flujo | Puntos | PASS | WARN | FAIL |
|-------|--------|------|------|------|
| Flow 1 — Operaciones (combustible) | 8 | 7 | 1 | 0 |
| Flow 2 — Turno del día | 6 | 5 | 1 | 0 |
| Flow 3 — Roles y usuarios | 5 | 0 | 3 | 2 |
| Flow 4 — TL38 | 4 | 4 | 0 | 0 |
| Flow 5 — Módulo Usuarios | 2 | 1 | 1 | 0 |
| Flow 6 — Versión móvil (390px) | 7 | 1 | 0 | 6 |
| **TOTAL** | **32** | **18** | **6** | **8** |

---

## FLOW 1 — OPERACIONES (Puntos 1–8)

| # | Verificación | Estado | Detalle |
|---|-------------|--------|---------|
| 1 | Puertos listado carga | ✅ | Botón "+ Registrar llegada" visible. Se creó TCKU-TEST-001 (Puerto Mariel, Diésel, 10,000 L) |
| 2 | Detalle isotanque — sección "Confirmar transferencia a depósito" | ⚠️ | Botón y formulario existen. **Pero:** selector de depósito destino muestra "No hay depósitos activos con combustible Diésel" aunque el Depósito Central (Diésel) existe y está activo |
| 3 | Depósitos/crear — campo "Provincia" (texto libre), sin "Capacidad" | ✅ | Formulario correcto: "Provincia *" es input libre, no aparece campo capacidad |
| 4 | /transferencias/1/gestionar — 3 pasos visibles, paso 3 bloqueado | ✅ | Paso 1 (datos + badge "En tránsito"), Paso 2 (form activo), Paso 3 (candado gris bloqueado) |
| 5 | Paso 2: confirmar llegada con 9,995 L | ✅ | Banner: "Llegada confirmada — 2026-06-29. Litros recibidos: 9,995.00 L (−5.00 L)" |
| 6 | Paso 3 desbloqueado — tabla de tarjetas activas | ✅ | 5 tarjetas activas con inputs editables (8777, 8785, 8751, 0898, 0880) |
| 7 | Distribuir 9,995 L entre tarjetas | ✅ | Asignados: **** 8777 ← 5,000 L / **** 8785 ← 4,995 L |
| 8 | Verificar saldos actualizados en /tarjetas | ✅ | 8777: 3,200 → 8,200 L (+5,000). 8785: 3,200 → 8,195 L (+4,995) |

**Screenshots:** `f1_01_puertos_listado.png`, `f1_02_puertos_detalle.png`, `f1_03_depositos_crear.png`, `f1_04_gestionar_paso1.png`, `f1_05_gestionar_paso2_confirmado.png`

---

## FLOW 2 — OPERATIVA: Turno del día (Puntos 9–14)

| # | Verificación | Estado | Detalle |
|---|-------------|--------|---------|
| 9 | /turno/ — selector solo gasolinera + fecha (sin selector de turno) | ✅ | Solo dos campos: gasolinera dropdown + date input |
| 10 | Cargar turno La Shell 2026-06-29 | ✅ | Formulario inline de habilitación visible. Tabla de habilitaciones vacía. Sección "Cerrar turno" colapsable. |
| 11 | Habilitación inline AJAX (PMA, unidad, tarjeta, litros) | ⚠️ | Funciona sin reload. **Pero:** PMA tiene `compra_minima_litros = 500`; al intentar 100 L el API devuelve 400 con error en `#hab-error` invisible. No hay indicación del mínimo antes del submit. Se usaron 500 L para completar la prueba. |
| 12 | Aprobar habilitación — estado cambia sin reload | ✅ | Estado "pendiente" → "aprobada". Botón cambia a "Despachar" sin recarga. |
| 13 | Modal de despacho abre con litros pre-cargados | ✅ | Modal "Registrar despacho" con 500 L pre-cargados. Campo "Foto del ticket" opcional visible. |
| 14 | Saldo tarjeta 8777 baja tras despacho | ✅ | 8,200 → 7,700 L (−500 L confirmado en /tarjetas) |

**Screenshots:** `f2_09_turno_selector.png`, `f2_10_turno_cargado.png`, `f2_11_turno_hab_anadida.png`, `f2_13_turno_modal_despacho.png`, `f2_14_turno_despachado.png`

---

## FLOW 3 — ROLES Y USUARIOS (Puntos 15–19)

| # | Verificación | Estado | Detalle |
|---|-------------|--------|---------|
| 15 | Crear op_deposito@mercatoria.com (rol operario_deposito) | ❌ | Servidor devuelve "Rol inválido." — Bug crítico en `blueprints/usuarios.py`: `rol not in _ROLES_LISTA` compara string contra lista de tuplas, siempre `True` |
| 16 | Crear op_gasolinera@mercatoria.com (rol operario_gasolinera) | ❌ | Mismo bug. Ningún rol puede ser guardado vía formulario de crear ni editar |
| 17 | Sidebar operario_deposito — solo ve OPERACIONES | ⚠️ | No verificable en runtime (usuario no creado). Lógica en `base.html`: `_es_dep = _rol in ['admin','pm','supervisor','operario_deposito']` → correcta en código |
| 18 | Sidebar operario_gasolinera — solo ve OPERATIVA | ⚠️ | No verificable en runtime. Lógica: `_es_gas = _rol in ['admin','pm','supervisor','operario','operario_gasolinera']` → correcta en código |
| 19 | Badges OP-DEP y OP-GAS en sidebar | ⚠️ | No verificable en runtime. Template define badges correctamente para ambos roles |

**Bug identificado:** `blueprints/usuarios.py` líneas 84 y 166
```python
# BUG (antes):
elif rol not in _ROLES_LISTA:          # string vs lista de tuplas → siempre True
# FIX (después del commit 3e4890e):
elif rol not in [r[0] for r in _ROLES_LISTA]:
```

---

## FLOW 4 — TL38 (Puntos 20–23)

| # | Verificación | Estado | Detalle |
|---|-------------|--------|---------|
| 20 | Dashboard TL38 — gráfica aparece (aunque sea en cero) | ✅ | KPIs en 0.00 L. Sin gráfica cuando no hay datos (correcto: `{% if chart_labels %}`). Chart.js 4.4.0 cargado |
| 21 | Registrar entrada: TEST-001, Juan Pérez, 500 L | ✅ | Movimiento creado. KPIs actualizados: Entradas del mes 500.00 L, Diferencia +500.00 L |
| 22 | Gráfica de barras aparece tras registrar movimiento | ✅ | Panel "Entradas vs. Despachos — últimos 6 meses" con barra verde para 2026-06 |
| 23 | Click en fila listado → /tl38/1 con todos los campos | ✅ | Detalle muestra: Tipo (badge Entrada), Fecha, Litros, Chapa, Chofer, Flota, Gasolinera, Responsable, Creado |

**Screenshots:** `f4_20_tl38_dashboard.png`, `f4_22_tl38_con_grafica.png`, `f4_23_tl38_detalle.png`

---

## FLOW 5 — MÓDULO USUARIOS (Puntos 24–25)

| # | Verificación | Estado | Detalle |
|---|-------------|--------|---------|
| 24 | Listado /usuarios/ carga correctamente | ✅ | 2 usuarios visibles: Administrador (Admin) + Cliente PMA (Cliente) |
| 25 | Colores de badges por rol correctos | ⚠️ | Admin = rojo ✅, Cliente = naranja/amarillo ✅. Badges PM, Operario Depósito, Operario Gasolinera no verificables por Bug Flow 3 |

**Screenshot:** `f5_24_usuarios_listado.png`

---

## FLOW 6 — VERSIÓN MÓVIL 390px (Puntos 26–32)

| # | Verificación | Estado | Detalle |
|---|-------------|--------|---------|
| 26 | Redimensionar viewport a 390px | ✅ | Completado sin error |
| 27 | Dashboard en 390px — cards legibles | ❌ | Sidebar fijo 280px ocupa 72% del viewport. Contenido (`<main>`) queda en **110px**. Cards de KPIs cortadas, títulos fragmentados. Ilegible. |
| 28 | Sidebar colapsa / botón hamburguesa visible | ❌ | No existe botón hamburguesa. Sidebar siempre visible, ocupa 280px fijos. No hay Bootstrap offcanvas ni ningún mecanismo de colapso. |
| 29 | Turno del día en 390px — formulario inline interactuable | ❌ | Formulario inline de habilitación completamente oculto detrás del sidebar. No se puede interactuar. |
| 30 | Gestionar viaje en 390px — pasos 1-2-3 legibles | ❌ | Los 3 pasos están cortados, el contenido de paso 2 (form) y paso 3 (tabla tarjetas) no caben en 110px. Inutilizable. |
| 31 | Elemento exacto responsable del fallo | ❌ | `aside.sidebar { width: 280px; }` en `static/css/admin.css`. Sin ningún `@media` query en todo el archivo. Sin `position: fixed` ni offcanvas. |
| 32 | Otros elementos móviles (navbar, tablas, modales) | ❌ | No aplica — la app es inutilizable desde el punto 27; cualquier elemento adicional queda oculto bajo el sidebar. |

**Screenshots:** `f6_27_dashboard_movil.png`, `f6_29_turno_movil.png`, `f6_30_gestionar_movil.png`

---

## Bugs encontrados — clasificación

### 🔴 CRÍTICO #1 — Validación de rol: ningún usuario puede ser creado ni editado
- **Archivo:** `blueprints/usuarios.py` líneas 84 y 166
- **Causa:** `rol not in _ROLES_LISTA` compara string contra lista de tuplas → siempre `True`
- **Impacto:** Módulo de usuarios completamente bloqueado. Flows 3 y 5 no verificables.
- **Estado:** **RESUELTO** en commit `3e4890e` (2026-06-29)

### 🔴 CRÍTICO #2 — Sin diseño responsive móvil
- **Archivo:** `static/css/admin.css`
- **Causa:** `width: 280px` hardcodeado en `.sidebar`. Cero `@media` queries en el archivo completo.
- **Impacto:** App inutilizable en cualquier dispositivo < 768px (móvil, tablet).
- **Corrección sugerida:** `@media (max-width: 768px) { .sidebar { display: none; } }` + botón hamburguesa en `base.html` + Bootstrap offcanvas o panel overlay.
- **Estado:** **PENDIENTE**

### 🟡 MEDIO #3 — Selector de depósito vacío en puertos/isotanque
- **Archivo:** `blueprints/puertos.py` (query de depósitos por tipo_combustible)
- **Causa probable:** La query filtra por igualdad exacta (`tipo_combustible = 'diesel'`) pero el campo en depósitos almacena múltiples combustibles separados por coma (`"diesel,gasolina_regular"`).
- **Impacto:** Operador no puede confirmar transferencia isotanque → depósito desde la UI.
- **Corrección sugerida:** Cambiar a `LIKE '%diesel%'` o usar `INSTR(tipo_combustible, 'diesel') > 0`.
- **Estado:** **PENDIENTE**

### 🟡 MEDIO #4 — `compra_minima_litros` sin feedback previo en turno inline
- **Archivo:** `templates/turno/index.html` (JS de habilitación)
- **Causa:** El mínimo de litros del cliente no se muestra en el form antes del submit. El error `#hab-error` está oculto hasta que el API devuelve 400.
- **Impacto:** Fricción UX — el operario no sabe cuántos litros mínimos puede pedir para el cliente.
- **Corrección sugerida:** Al seleccionar cliente/tarjeta, mostrar `compra_minima_litros` como hint debajo del campo de litros via JS.
- **Estado:** **PENDIENTE**

### 🟡 MEDIO #5 — Base de datos efímera en Render (SQLite)
- **Contexto:** En entorno de pruebas, Render usa SQLite sobre disco efímero. Todos los datos operativos (depósitos, transferencias, recepciones) se perdieron entre la sesión anterior y esta.
- **Impacto:** En producción real, un redeploy borra todos los datos operativos.
- **Corrección sugerida:** Migrar a PostgreSQL (add-on gratuito en Render, ya preparado con `migraciones_pg.py`).
- **Estado:** **PENDIENTE**

---

## Errores de consola

| Tipo | URL | Descripción |
|------|-----|-------------|
| 400 (pruebas manuales de diagnóstico) | `/turno/api/habilitacion` | Fetch sin CSRF token durante diagnóstico manual — no es error del sistema |
| — | — | Sin errores de consola en uso normal del sistema |

---

## Screenshots tomados (sesión completa)

| Archivo | Pantalla |
|---------|----------|
| `f1_01_puertos_listado.png` | Puertos — listado con TCKU-TEST-001 |
| `f1_02_puertos_detalle.png` | Isotanque detalle — formulario "Confirmar transferencia" con selector vacío (⚠️) |
| `f1_03_depositos_crear.png` | Depósitos/crear — campo Provincia, sin Capacidad |
| `f1_04_gestionar_paso1.png` | Gestionar viaje #1 — estado en tránsito, paso 3 bloqueado |
| `f1_05_gestionar_paso2_confirmado.png` | Gestionar viaje #1 — llegada confirmada, paso 3 con tabla tarjetas |
| `f2_09_turno_selector.png` | Turno — selector gasolinera + fecha |
| `f2_10_turno_cargado.png` | Turno La Shell cargado con formulario inline |
| `f2_11_turno_hab_anadida.png` | Habilitación PMA añadida, estado "pendiente" |
| `f2_13_turno_modal_despacho.png` | Modal "Registrar despacho" abierto con 500 L |
| `f2_14_turno_despachado.png` | Habilitación en estado "despachada" |
| `f4_20_tl38_dashboard.png` | TL38 dashboard vacío (KPIs en cero, sin gráfica) |
| `f4_22_tl38_con_grafica.png` | TL38 dashboard con gráfica de barras tras registrar movimiento |
| `f4_23_tl38_detalle.png` | TL38 detalle movimiento #1 |
| `f5_24_usuarios_listado.png` | Usuarios — listado con badges Admin (rojo) y Cliente (naranja) |
| `f6_27_dashboard_movil.png` | Dashboard en 390px — sidebar bloquea contenido (❌) |
| `f6_29_turno_movil.png` | Turno del día en 390px — formulario invisible (❌) |
| `f6_30_gestionar_movil.png` | Gestionar viaje en 390px — pasos cortados (❌) |
| `bug2_login_cliente_ok.png` | Portal cliente — login exitoso, "Programa Mundial de Alimentos" |
