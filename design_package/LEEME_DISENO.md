# Paquete de Diseño — Mercatoria Fuel
**Versión:** 1.0 · **Fecha:** 2026-07-10 · **Preparado por:** Claude Code

Este paquete contiene todo lo que un diseñador necesita para rediseñar Mercatoria Fuel.
Los archivos fuente incluidos son copias exactas del código en producción al momento de generación.

---

## Contenido del paquete

```
design_package/
├── LEEME_DISENO.md          ← este archivo
├── design_audit.md          ← inventario visual completo + deuda técnica
├── design_tokens.json       ← tokens actuales en formato machine-readable
├── css/
│   └── admin.css            ← sistema de diseño del panel (497 líneas)
└── templates/
    ├── base.html            ← layout base del panel interno
    ├── base_cliente.html    ← layout base del portal cliente
    ├── base_tienda.html     ← layout base de la tienda (con CSS inline)
    ├── landing.html         ← página pública (dark, CSS inline)
    └── login.html           ← página de login (CSS inline)
```

---

## El sistema en una oración

**Mercatoria Fuel** es un sistema de gestión de combustible (Flask + Jinja2) con cuatro contextos visuales distintos: panel operativo interno, portal cliente, tienda online, y páginas públicas. No tiene build step — todo el CSS es archivos estáticos o inline en templates.

---

## Cuatro contextos, cuatro paletas

| Contexto | Base template | CSS | Tema | Acento |
|---|---|---|---|---|
| Panel interno | `base.html` | `admin.css` externo | Claro, azul | `#155eef` |
| Portal cliente | `base_cliente.html` | mismo `admin.css` | Idéntico al panel | `#155eef` |
| Tienda | `base_tienda.html` | Inline en template | Claro, naranja | `#E86A2C` |
| Landing + Auth | `landing.html`, `login.html` | Inline en cada uno | Landing dark, login claro | `#E86A2C` |

El naranja `#E86A2C` es el color de marca real de Mercatoria. El azul `#155eef` que domina el panel es probablemente herencia de un template genérico — esto es deuda visual documentada en `design_audit.md`.

---

## Lo que PUEDE modificarse libremente

- **`admin.css`:** todos los valores de variables CSS (colores, radios, sombras, tipografía)
- **Las clases CSS** propias (`.panel`, `.btn`, `.badge`, `.kpi-card`, `.data-table`, `.sidebar`, etc.)
- **Estructura HTML** de los templates base (layout, navegación, estructura del header)
- **Imágenes** en `static/img/` (solo hay `favicon.png` actualmente)
- **Bootstrap:** puede reemplazarse, eliminarse, o actualizarse — no hay componentes Bootstrap en uso real

---

## LO QUE NO SE PUEDE TOCAR

### 1. Archivos PWA / service worker
Aunque actualmente no existen `sw.js` ni `manifest.json` en el repo (verificado), si se agregan en el futuro para instalación móvil, **nunca borrar ni modificar estos archivos** durante el rediseño. Afectan la instalación de la PWA en dispositivos móviles.

Archivos de la lista prohibida (si aparecen):
- `static/sw.js`
- `static/manifest.json`
- `static/manifest.webmanifest`
- Cualquier `<link rel="manifest">` en templates

### 2. Atributos `data-*` con lógica JavaScript

Los siguientes atributos están leídos programáticamente por JS en runtime. Si se renombran o eliminan, el JS se rompe **sin arrojar error visible** en la consola — simplemente deja de funcionar.

| Atributo | Dónde existe | JS que lo lee | Qué hace |
|---|---|---|---|
| `data-saldo-usable` | `<form id="form-editar-tarjeta">` en `templates/tarjetas/editar.html` | `avisarCambioGasolinera()` | Muestra litros disponibles al cambiar gasolinera |
| `data-saldo-retenido` | idem | idem | Incluye saldo retenido en el aviso |
| `data-gasolinera-original` | idem | idem | Detecta si la gasolinera cambió |
| `data-saldo` | Elementos en templates de reasignación | JS de reasignación | Valor de saldo para cálculos |
| `data-gasolinera` | Elementos en templates de reasignación | JS de reasignación | Gasolinera de referencia |

**Regla:** Al rediseñar el HTML de los templates, mantener estos atributos exactamente como están. Pueden agregar otros `data-*` libremente; solo no renombrar ni eliminar los listados.

### 3. URLs de rutas Flask (`href`, `action`, `src`)
Las rutas como `/tarjetas`, `/gasolineras`, `/despachos/crear`, etc. están hardcodeadas en los templates y son definidas por Flask en los blueprints. No cambiar estas URLs al rediseñar — solo se puede cambiar el texto visible del link o del botón.

### 4. Variables de Jinja2 (`{{ variable }}`, `{% if %}`, etc.)
Todo el código Jinja2 entre `{%` y `%}` o `{{` y `}}` es lógica de backend. El rediseño puede mover estas expresiones a otro lugar del HTML, pero no modificar las variables mismas.

### 5. Los bloques `{% block %}` de los templates base
Los templates hijos extienden el base con `{% block contenido %}`, `{% block scripts %}`, etc. No renombrar estos bloques sin actualizar también todos los templates hijos (son decenas).

---

## Recomendaciones prioritarias para el rediseño

Tomadas del `design_audit.md`:

1. **Convertir `#E86A2C` en variable CSS** — actualmente hardcodeado en 9+ lugares
2. **Crear sistema de alerts reutilizable** — actualmente son `style=""` inline repetidos en cada template
3. **Unificar paleta de texto** — `#172033` vs `#111827` vs `#374151` son el mismo gris con tres valores
4. **Cargar Inter explícitamente** — si se quiere usar, agregar Google Fonts o `@font-face` con la fuente local
5. **Decidir si mantener Bootstrap** — actualmente es ~30 KB de CSS muerto. El JS bundle sí se usa (sidebar móvil)
6. **Dar identidad propia al portal cliente** — actualmente es visual-idéntico al panel interno

---

## Cómo leer `admin.css`

El archivo tiene 497 líneas divididas en secciones (en orden):

1. `:root` — variables CSS (tokens de color, tamaños, sombra)
2. `*` reset + `body` base
3. `.sidebar` + sub-elementos (nav items, badges, logo)
4. `.topbar`
5. `.main-content`
6. `.page-header`
7. `.panel` + `.panel-header`
8. `.kpi-grid` + `.kpi-card` + `.kpi-icon`
9. `.btn-*`
10. `.form-*` (`.form-label`, `.form-control`, `.form-grid`)
11. `.data-table` + headers/rows/cells
12. `.badge-*`
13. `.role-badge`
14. `@media (max-width: 768px)` — responsive

No hay ninguna clase con nombre Bootstrap. Todo es custom.

---

## Herramientas de diseño sugeridas

Para el rediseño se puede usar cualquier herramienta. El CSS resultante debe ser un archivo externo en `static/css/`. El paquete de entrega esperado es:

- `static/css/nuevo_sistema.css` (o `admin_v2.css`) — nuevo sistema de diseño
- `templates/base.html` modificado — apuntando al nuevo CSS
- Instrucciones de migración para los templates inline (tienda, landing, login)

No se espera un build step. Bootstrap puede mantenerse (solo actualizar versión a 5.3.3 consistente) o eliminarse.
