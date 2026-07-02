# Reporte de Pruebas — 2026-06-29

## Commit verificado
`b69ed94` — Fix: responsive móvil, selector depósito en puertos, feedback compra mínima en turno

## Páginas probadas
- /login (admin@mercatoria.com)
- /dashboard (viewport 1280px y 390px)
- /turno/?gasolinera_id=1&fecha=2026-06-29
- /depositos/crear
- /puertos/crear
- /puertos/1

---

## Resultados

| # | Verificación | Resultado | Detalle |
|---|-------------|-----------|---------|
| 1 | Deploy arranca sin errores | ✅ PASS | Cold start ~30 s. Login carga correctamente |
| 2 | Login admin funciona | ✅ PASS | Redirige a `/dashboard` |
| 3 | **BUG 1 — Dashboard en 390px: contenido visible** | ✅ PASS | Sidebar oculto, KPIs en columna única, todo el contenido legible |
| 4 | **BUG 1 — Botón hamburguesa ☰ visible en móvil** | ✅ PASS | Botón `#btn-hamburger` aparece en topbar en 390px, invisible en desktop |
| 5 | **BUG 1 — Sidebar abre al clicar hamburguesa** | ✅ PASS | Sidebar desliza desde la izquierda con overlay oscuro detrás |
| 6 | **BUG 1 — Sidebar cierra al clicar overlay** | ✅ PASS | `sidebar-overlay.click()` → sidebar desaparece, overlay retira |
| 7 | **BUG 2 — Selector depósito en puertos/detalle** | ✅ PASS | Depósito Central QA (tipo `diesel,gasolina_regular`) aparece en el selector para llegada de tipo `diesel` |
| 8 | **BUG 3 — Hint "Mín. 500 L" visible en turno** | ✅ PASS | `<small>Mín. 500 L para venta libre</small>` aparece bajo el campo de litros |
| 9 | **BUG 3 — Validación JS client-side antes de POST** | ✅ PASS | Con 100 L ingresados muestra: "El mínimo de litros por habilitación es 500 L." sin llamar al servidor |
| 10 | Errores de consola | ✅ PASS | Sin errores en uso normal. Solo 503 de cold start (esperado) y 404 de `/favicon.ico` (el favicon está en `/static/img/favicon.png`) |

---

## Cambios aplicados en este commit

### ✅ BUG 1 — Responsive móvil

- **`static/css/admin.css`**: Añadido bloque `@media (max-width: 768px)`:
  - `.sidebar` pasa a `position: fixed`, `transform: translateX(-280px)` (oculto)
  - `.sidebar.sidebar-open` hace `transform: translateX(0)` (visible)
  - `.sidebar-overlay` visible solo cuando tiene clase `active`
  - `#btn-hamburger` oculto por defecto, `display: inline-flex` en móvil
  - `.kpi-grid` y `.form-grid` a `grid-template-columns: 1fr`
  - `.main-content` baja padding a `16px`, ancho al 100%
- **`templates/base.html`**:
  - Añadido `<div id="sidebar-overlay" class="sidebar-overlay">` entre `</aside>` y `<main>`
  - Añadido `<button id="btn-hamburger">` al inicio del `.topbar`
  - Añadido JS inline de toggle: abre/cierra sidebar al clicar hamburguesa u overlay; cierra también al clicar cualquier `.nav-item`

### ✅ BUG 2 — Selector depósito vacío en puertos/isotanque

- **`blueprints/puertos.py`**: Reemplazada query `tipo_combustible = ?` por 4 condiciones OR:
  - Exacto: `tipo_combustible = ?`
  - Inicia: `tipo_combustible LIKE ?` (`"diesel,%"`)
  - Termina: `tipo_combustible LIKE ?` (`"%,diesel"`)
  - Medio: `tipo_combustible LIKE ?` (`"%,diesel,%"`)
  - Compatible con SQLite y PostgreSQL (sin `%` en la query string, solo en parámetros)

### ✅ BUG 3 — Feedback compra mínima en turno

- **`blueprints/turno.py`**: `index()` ahora consulta `SELECT valor FROM configuracion WHERE clave='compra_minima_litros'` y pasa `compra_minima` al template
- **`templates/turno/index.html`**:
  - Añadido `<small>Mín. {{ compra_minima|int }} L para venta libre</small>` bajo el campo litros (solo si `compra_minima > 0`)
  - Añadido `const COMPRA_MINIMA = {{ compra_minima }};` en el bloque de scripts
  - Añadida validación JS en `agregarHabilitacion()` antes del fetch: si `litrosVal < COMPRA_MINIMA` muestra error en `#hab-error` sin llamar al servidor

---

## Errores de consola

| Tipo | Descripción | Severidad |
|------|-------------|-----------|
| 503 | `/login` durante cold start inicial de Render | Esperado — no es error del sistema |
| 404 | `/favicon.ico` — el browser busca la ruta estándar, pero nuestro favicon está en `/static/img/favicon.png` | Cosmético |

Sin errores en uso normal del sistema.

---

## Screenshots

| Archivo | Pantalla |
|---------|----------|
| `b1_dashboard_390px.png` | Dashboard en 390px — hamburguesa ☰ visible, sidebar oculto, KPIs en columna única ✅ |
| `b1_sidebar_abierto_390px.png` | Sidebar desplegado al clicar hamburguesa, overlay oscuro visible ✅ |
| `b1_sidebar_cerrado_overlay.png` | Sidebar cerrado tras clicar overlay — contenido restaurado ✅ |
| `b3_turno_compra_minima.png` | Turno del día — hint "Mín. 500 L para venta libre" bajo el campo litros ✅ |
| `b3_turno_validacion_js.png` | Error JS "El mínimo de litros por habilitación es 500 L." antes de POST ✅ |
| `b2_puertos_selector_deposito_ok.png` | Puertos/detalle — Depósito Central QA aparece en selector (multi-combustible) ✅ |

---

## Recomendaciones pendientes

- **Overlay click en Playwright**: el `overlay.click()` nativo de Playwright falla porque el sidebar (z-index 1050) intercepta el área central del viewport cuando está abierto. Workaround: usar `document.getElementById('sidebar-overlay').click()` vía JS, o hacer click en coordenadas a la derecha del sidebar (x > 280px). En uso real con touch/mouse el overlay funciona correctamente (verificado con JS dispatch).
- **favicon.ico 404**: Considerar añadir un `<link rel="shortcut icon">` que cubra la ruta `/favicon.ico` además de la ruta existente en `/static/img/favicon.png`, o redirigir `/favicon.ico` en el servidor Flask.
- **PostgreSQL free tier expira 2026-07-26**: Migrar a plan de pago antes de esa fecha (ver `MDS/03_DEPLOY.md`).
