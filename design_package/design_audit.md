# Auditoría Visual — Mercatoria Fuel
> Verificado contra el código fuente real el 2026-07-10.
> Archivo de referencia para el rediseño. Todo lo aquí descrito refleja lo que existe actualmente en el repositorio, no un estado ideal.

---

## 1. Stack técnico frontend

| Capa | Tecnología | Versión | Cómo se carga |
|---|---|---|---|
| Framework CSS | Bootstrap | 5.3.0 (panel+cliente) / 5.3.3 (tienda+landing+login) | CDN jsDelivr |
| CSS propio (panel) | `static/css/admin.css` | — | `<link>` estático |
| CSS propio (tienda) | Inline en `base_tienda.html` | — | `<style>` en `<head>` |
| CSS propio (landing) | Inline en `landing.html` | — | `<style>` en `<head>` |
| CSS propio (login/auth) | Inline en `login.html` | — | `<style>` en `<head>` |
| Iconos | Bootstrap Icons | 1.11.3 | CDN jsDelivr |
| Tipografía | Sistema (`Inter, Segoe UI, Arial`) | — | Sin carga de fuente externa |
| Build step | **Ninguno** | — | HTML directo de Flask/Jinja2 |
| Node.js / npm | **No existe** | — | — |

**Bootstrap se carga pero casi no se usa.** La UI real se construye 100% con clases propias (`.panel`, `.btn-primary`, `.kpi-card`, `.data-table`…). Bootstrap aporta solo el CSS reset y el JS bundle para el sidebar móvil. Es ~30 KB de CSS muerto que puede eliminarse en el rediseño.

---

## 2. Los cuatro contextos visuales del sistema

El proyecto NO tiene un único sistema de diseño unificado. Tiene **cuatro contextos con CSS separado**:

### 2.1 Panel operativo interno
- **Base:** `templates/base.html`
- **CSS:** `static/css/admin.css` (497 líneas)
- **Layout:** Sidebar fijo 280px izquierda + `main-content` con flex-grow
- **Tema:** Claro, fondo `#f4f6fb`, acento azul `#155eef`
- **Usuarios:** admin, pm, puesto_de_mando, operador_gasolinera, supervisor

### 2.2 Portal cliente
- **Base:** `templates/base_cliente.html`
- **CSS:** Mismo `admin.css` que el panel interno
- **Layout:** Idéntico al panel — sidebar + main
- **Tema:** Idéntico al panel interno. **Sin diferenciación visual propia.**
- **Usuarios:** clientes externos (empresas con habilitaciones)

### 2.3 Tienda online
- **Base:** `templates/base_tienda.html`
- **CSS:** 112 líneas inline en `<head>`. Sin `admin.css`.
- **Layout:** Top-nav sticky + `tienda-main` centrado max-width 1000px
- **Tema:** Claro, fondo `#F3F4F6`, acento naranja `#E86A2C`
- **Usuarios:** clientes en flujo de compra/reserva online

### 2.4 Páginas públicas (landing + auth)
- **Base:** Sin base compartida — cada página es standalone
- **CSS:** 100% inline en cada archivo (`landing.html`, `login.html`)
- **Layout landing:** Dark hero + secciones centradas
- **Tema landing:** **Oscuro**, fondo `#0F1117`, texto claro
- **Tema login/registro:** Claro, card centrado, fondo `#F3F4F6`

---

## 3. Tokens de diseño actuales (panel interno)

### Colores — variables CSS en `admin.css`

| Variable | Valor | Uso |
|---|---|---|
| `--bg` | `#f4f6fb` | Fondo de página |
| `--panel` | `#ffffff` | Superficie de cards y paneles |
| `--panel-soft` | `#f8fafc` | Cabecera de tablas, fondos suaves |
| `--text` | `#172033` | Texto principal |
| `--muted` | `#64748b` | Texto secundario, labels |
| `--primary` | `#155eef` | Botón primario, focus ring, links activos |
| `--primary-dark` | `#0f3ea8` | Hover de primario |
| `--border` | `#e5e7eb` | Bordes de paneles, separadores de tabla |
| `--danger` | `#dc2626` | Errores, estados críticos |
| `--success` | `#16a34a` | Confirmaciones, estados OK |
| `--warning` | `#f59e0b` | Alertas, saldos bajos |
| `--info` | `#0891b2` | Información, badges de combustible |
| `--sidebar` | `#0f172a` | Fondo sidebar (near-black azul marino) |
| `--sidebar-soft` | `#102a56` | Color inferior del gradiente del sidebar |
| `--shadow` | `0 14px 35px rgba(15,23,42,0.08)` | Sombra de paneles |
| `--radius` | `18px` | Border-radius de paneles |

### Colores hardcoded (no son variables — deuda visual)

| Valor | Dónde aparece |
|---|---|
| `#E86A2C` | Nav item activo, nav-badge, sidebar-badge, logo SVG (4 rects), login brand, focus ring tienda/login |
| `#F5A623` | Logo SVG (4 rects alternos), `.product-price` en landing |
| `#C45520` | Hover de naranja en tienda/landing/login |
| `#475569` | Color de texto en `<th>` de tablas (hardcoded, no es `--muted`) |
| `#F9FAFB` | Hover de filas en tienda (similar pero distinto a `--panel-soft: #f8fafc`) |
| `#374151` | Labels de formulario en tienda/login (no es `--text`) |
| `#D1D5DB` | Border de inputs en tienda/login (no es `--border`) |
| `#111827` | `--text` en tienda (distinto de `#172033` en panel) |
| `#6B7280` | `--muted` en tienda (igual que `#64748b` del panel, pero hardcoded) |
| `#0F1117` | Fondo dark de landing (sin variable) |
| `#9CA3AF` | Texto descriptivo en landing (sin variable) |

### Tipografía

| Contexto | Stack declarado | Fuente real en la mayoría de sistemas |
|---|---|---|
| Panel / Portal cliente | `Inter, "Segoe UI", Arial, sans-serif` | Segoe UI (Inter no se carga externamente) |
| Tienda / Login / Landing | `'Segoe UI', system-ui, sans-serif` | Segoe UI |

> **Nota:** `Inter` está en primer lugar en `admin.css` pero no se carga con `@font-face` ni CDN. En sistemas que no lo tienen instalado (la mayoría de Windows pre-11) renderiza como Segoe UI.

### Espaciado y radios

| Elemento | Valor |
|---|---|
| Border-radius panels | `18px` (`--radius`) |
| Border-radius botones | `11px` (`.btn`), `8px` (`.btn-sm`) |
| Border-radius inputs | `11px` (`.form-control`) |
| Border-radius badges | `999px` (píldora) |
| Border-radius sidebar nav items | `13px` |
| Border-radius KPI icon | `14px` |
| Padding main content | `38px` (desktop), `16px` (móvil) |
| Ancho sidebar | `280px` fijo |
| Max-width tienda | `1000px` centrado |

---

## 4. Catálogo de componentes

### Botones (`.btn` + modificador)

| Clase | Color | Uso |
|---|---|---|
| `.btn-primary` | Fondo `#155eef`, texto blanco | Acción principal |
| `.btn-success` | Fondo `#16a34a`, texto blanco | Confirmar / asignar |
| `.btn-danger` | Fondo `#dc2626`, texto blanco | Eliminar / desactivar |
| `.btn-soft` | Fondo `#eef4ff`, texto `#155eef` | Ver detalle, acciones secundarias |
| `.btn-secondary` | Fondo `#f1f5f9`, texto `#475569` | Cancelar, volver, filtros |
| `.btn-sm` | Reduce padding y font-size | Dentro de tablas |

### Badges (`.badge` + modificador)

| Clase | Color | Uso |
|---|---|---|
| `.badge-ok` | Fondo `#D1FAE5`, texto `#065F46` | Estado activo / confirmado |
| `.badge-warn` | Fondo `#FEF3C7`, texto `#92400E` | Alerta / pendiente |
| `.badge-danger` | Fondo `#FEE2E2`, texto `#991B1B` | Error / bloqueado |
| `.badge-info` | Fondo `#DBEAFE`, texto `#1E40AF` | Información / tipo combustible |
| `.badge-neutral` | Fondo `#F3F4F6`, texto `#6B7280` | Inactivo / neutral |

### Roles (`.role-badge` + modificador)

| Clase | Color | Rol |
|---|---|---|
| `.role-admin` | Fondo `#fee2e2`, texto `#991b1b` | admin |
| `.role-pm` | Fondo `#dbeafe`, texto `#1e40af` | pm |
| `.role-operario` | Fondo `#dcfce7`, texto `#166534` | operario |
| `.role-operario-deposito` | Fondo `#d1fae5`, texto `#065f46` | puesto_de_mando |
| `.role-operario-gasolinera` | Fondo `#bbf7d0`, texto `#14532d` | operador_gasolinera |
| `.role-supervisor` | Fondo `#f1f5f9`, texto `#475569` | supervisor |
| `.role-cliente` | Fondo `#ffedd5`, texto `#9a3412` | cliente |

### Alerts inline (hardcoded en templates, sin clase reutilizable)

Los templates usan `style=""` inline para alerts — no hay clase CSS propia:

| Color borde | Fondo | Texto | Uso semántico |
|---|---|---|---|
| `#16A34A` | `#F0FDF4` | `#15803D` / `#14532D` | Éxito / OK |
| `#DC2626` | `#FEF2F2` | `#991B1B` | Error |
| `#CA8A04` | `#FEF9C3` | `#713F12` | Aviso descartable |
| `#3B82F6` | `#EFF6FF` | `#1E40AF` | Informativo |
| `#F59E0B` | `#FFFBEB` | `#92400E` | Advertencia |

### Iconos KPI (`.kpi-icon` + modificador)

| Clase | Color icon | Fondo |
|---|---|---|
| `.kpi-icon.primary` | `#155eef` | `#eef4ff` |
| `.kpi-icon.success` | `#16a34a` | `#ecfdf3` |
| `.kpi-icon.warning` | `#f59e0b` | `#fffbeb` |
| `.kpi-icon.info` | `#0891b2` | `#ecfeff` |
| `.kpi-icon.neutral` | `#475569` | `#f1f5f9` |
| `.kpi-icon.danger` | `#dc2626` | `#fee2e2` |

---

## 5. Deuda visual — inconsistencias a resolver en el rediseño

Estas no son opiniones: son hechos verificados en el código. El rediseño debería resolver todas.

### 5.1 El naranja de marca no es una variable CSS
`#E86A2C` aparece hardcoded en al menos 9 lugares en `admin.css` y en todos los templates de auth/landing. Si cambia el naranja hay que buscar y reemplazar manualmente en múltiples archivos. **Acción: convertirlo en `--brand` o `--orange` en `admin.css`.**

### 5.2 Cuatro sistemas CSS paralelos sin token compartido
`admin.css`, `base_tienda.html` inline, `landing.html` inline, `login.html` inline. Los cuatro definen colores similares con valores ligeramente distintos (ej. `--text: #172033` vs `#111827` vs `#374151`) y no comparten ningún archivo fuente. **Acción: un archivo de tokens compartido.**

### 5.3 Bootstrap duplicado e inconsistente
El panel carga Bootstrap 5.3.0, el resto carga 5.3.3. En la práctica ningún módulo funcional de Bootstrap se usa — solo el reset y el JS bundle. Si el rediseño usa un sistema propio, Bootstrap puede eliminarse. **Riesgo a evaluar: el JS bundle se usa para el sidebar hamburger en móvil.**

### 5.4 Inter declarada pero no cargada
`font-family: Inter, "Segoe UI", Arial` en `admin.css` pero sin `@font-face` ni CDN. En la mayoría de Windows renderiza como Segoe UI. Si el rediseño usa Inter, debe cargarse explícitamente (Google Fonts, Bunny Fonts, o font-face local).

### 5.5 Alerts sin clase — style inline disperso
Las notificaciones de éxito/error/aviso se implementan con `style="background:#F0FDF4;border-left:4px solid #16A34A..."` repet ido en cada template. No hay una clase `.alert-success` en `admin.css`. **Resultado: si cambia el color de éxito, hay que editar decenas de templates.**

### 5.6 Colores de estado hardcodeados en templates
Valores como `#D97706` (amber para saldo bajo), `#16A34A` (verde para saldo positivo), `#E86A2C` (naranja para valores críticos) aparecen en `style=""` inline dentro de las celdas de tablas. No son variables. **Acción: token semántico por estado (`--color-estado-ok`, `--color-estado-bajo`, etc.).**

### 5.7 Portal cliente sin identidad visual propia
`base_cliente.html` usa exactamente el mismo `admin.css` que el panel interno. Un cliente externo ve la misma UI que un operario interno. No hay diferenciación de contexto. **Oportunidad: en el rediseño, dar identidad propia al portal.**

### 5.8 Panel vs tienda: paletas divergentes
El panel usa azul `#155eef` como primario. La tienda usa naranja `#E86A2C`. Son el mismo producto pero con accent colors diferentes. El naranja es la identidad de marca correcta; el azul del panel parece herencia de un template genérico.

### 5.9 Valores de border-radius inconsistentes
Paneles: 18px. Botones: 11px. Inputs: 11px. Sidebar items: 13px. KPI icon: 14px. Ninguno es múltiplo consistente de un base unit. **Acción: escala de radios en 4px increments (8/12/16/20/999).**

### 5.10 Landing en tema oscuro, todo lo demás en claro
La página pública (`landing.html`) tiene fondo `#0F1117` (dark). Al hacer login, el usuario aterriza en el panel blanco/claro. Salto visual brusco sin transición.

---

## 6. Data-* attributes con lógica JS (NO tocar en rediseño)

Estos atributos están leídos programáticamente por JavaScript. Si se renombran o eliminan durante el rediseño HTML, el JS se rompe sin error visible:

| Atributo | En elemento | JS que lo lee | Efecto si se rompe |
|---|---|---|---|
| `data-saldo-usable` | `<form id="form-editar-tarjeta">` | `avisarCambioGasolinera()` en tarjetas/editar.html | El aviso de saldo al cambiar gasolinera deja de mostrar los litros |
| `data-saldo-retenido` | idem | idem | idem |
| `data-gasolinera-original` | idem | idem | El aviso no detecta si cambió de gasolinera |
| `data-saldo` | Elementos en reasignar templates | JS de reasignación | Pierde el valor de saldo para cálculos |
| `data-gasolinera` | Elementos en reasignar templates | JS de reasignación | Pierde la gasolinera de referencia |

---

## 7. Assets existentes

| Archivo | Tipo | Uso |
|---|---|---|
| `static/img/favicon.png` | PNG | Favicon en todos los contextos |
| `static/css/admin.css` | CSS | Sistema de diseño del panel |
| `static/uploads/tickets/` | PNGs dinámicos | Fotos de tickets de despacho — no modificar estructura |

**No existen:** fuentes custom, sprites, SVG icons (se usan Bootstrap Icons vía CDN), archivos JS propios en `static/` (todo el JS está inline en templates o cargado vía CDN).
