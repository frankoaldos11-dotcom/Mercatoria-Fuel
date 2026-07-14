# Design tokens — Mercatoria Fuel

Fuente de verdad de los design tokens del sitio. Esta carpeta es autocontenida: un diseñador
puede editar solo los `.json` de acá y regenerar el CSS sin tocar lógica de la app ni
templates. Estructura y pipeline calcados de `mercatoria-trucks/tokens/` — Fuel hereda el
vocabulario de nombres que Truck definió primero.

## Qué hay en cada archivo

| Archivo | Contiene | Convención de nombres |
|---|---|---|
| `color.json` | Roles de marca y semánticos, planos (sin superficie) — `principal`, `activo`, `panel`, `peligro`/`exito`/`aviso`/`info`, `barra-lateral`, más los tenues/oscuros derivados (`fondo-*-suave`, `*-oscuro`, `texto-sobre-*`) | Español, vocabulario compartido con Truck |
| `color-superficie.json` | Los 4 neutros (`fondo`, `texto`, `atenuado`, `borde`) que en Fuel tienen valor **distinto** entre la superficie staff y la superficie cliente | Español + superficie: `--{rol}-staff` / `--{rol}-cliente` |
| `color-sin-mapeo.json` | ~49 tokens de color de la Tanda 0 sin rol claro en el vocabulario compartido (variantes de un solo uso de alertas/badges, duplicados de capitalización) | Sin traducir — mantienen el nombre `color-*` original |
| `typography.json` | Font-family por superficie, escala de tamaños (staff en `px`, cliente en `rem`), escala de pesos, más los tamaños/pesos fuera de la escala de 6/4 pasos | `fuente-*`, `texto-*-staff`/`texto-*-cliente`, `peso-*` |
| `spacing.json` | Escala de espaciado de 6 pasos + 3 valores intermedios sin slot | `espacio-*` |
| `effects.json` | Radios (6 pasos + 4 sin slot) y sombras (3 pasos) | `radio-*`, `sombra-*` |

Todos los valores son los que ya inventarió `static/css/tokens.css` en la Tanda 0 (commit
`39f4d8c`), grepeados en su momento contra `admin.css` y los templates — no son valores de
diseño nuevos. Esta tanda **no cambia ningún valor**, solo nombres (con una única excepción
documentada: `fuente-landing`, ver abajo).

## Vocabulario compartido con Mercatoria Truck

Truck define el vocabulario primero (`mercatoria-trucks/tokens/README.md`); Fuel lo hereda.
Mismos **nombres de escalón**, valores propios de cada app.

| Categoría | Prefijo | Escalones | Ejemplo |
|---|---|---|---|
| Color de marca/semántico | `principal`, `activo`, `panel`, `peligro`, `exito`, `aviso`, `info`, `barra-lateral` | — | `--principal` |
| Neutro por superficie | `fondo`, `texto`, `atenuado`, `borde` | `staff` / `cliente` | `--fondo-staff` |
| Familia tipográfica | `fuente-*` | `staff` / `cliente` / `landing` | `--fuente-staff` |
| Tamaño de texto | `texto-*` | `xs` `sm` `md` `lg` `xl` `2xl`, **por superficie en Fuel** (ver más abajo) | `--texto-md-staff` |
| Peso de fuente | `peso-*` | `regular` `semibold` `bold` `extrabold` | `--peso-bold` |
| Espaciado | `espacio-*` | `xs` `sm` `md` `lg` `xl` `2xl` | `--espacio-md` |
| Radio de borde | `radio-*` | `sm` `md` `lg` `xl` `2xl` `pill` | `--radio-md` |
| Sombra | `sombra-*` | `sm` `md` `lg` | `--sombra-md` |

Truck también tiene `panel-suave`, `principal-oscuro`, `barra-lateral-suave` (no listados en el
resumen inicial de este pedido, pero sí en su catálogo real) — Fuel los adopta también, y sus
valores coinciden literalmente con los que Truck documenta como sus propios valores
**pre-rebrand de Adrián** (`admin.css` de Fuel y el `admin.css` original de Truck comparten el
mismo `:root` de origen).

## Por qué `admin.css` de Fuel fue la referencia principal para el mapeo

`admin.css` ya tiene su propio `:root` (`--bg`, `--panel`, `--text`, `--primary`, `--danger`,
`--success`, `--warning`, `--info`, `--sidebar`, etc.) — 16 valores que coinciden **exacto**
con lo que Truck documenta como su set pre-rebrand. Eso da alta confianza en el mapeo del
núcleo: no es una analogía, son los mismos números, confirmados también con grep sobre el uso
real de cada hex en `admin.css` y templates.

## Mapeo completo

### Núcleo — mapeo directo (`color.json` + `color-superficie.json`)

| Nombre viejo (Tanda 0) | Nombre nuevo | Valor |
|---|---|---|
| `--color-brand-blue` | `--principal` | `#F16A30` (corregido — ver "Corrección: naranja de marca" abajo; el valor original de Tanda 1 era `#155eef`, el azul que `admin.css` llamaba `--primary`) |
| `--color-brand-blue-dark` | `--principal-oscuro` | `#0f3ea8` (sin cambios — ver más abajo) |
| `--color-brand-orange` | `--activo` | `#F16A30` (corregido junto con `--principal`; el valor original de Tanda 1 era `#E86A2C`) |
| `--color-white` | `--panel` | `#ffffff` |
| `--color-danger-strong-lower` | `--peligro` | `#dc2626` |
| `--color-success-strong-lower` | `--exito` | `#16a34a` |
| `--color-warning-strong-lower` | `--aviso` | `#f59e0b` |
| `--color-info-strong` | `--info` | `#0891b2` |
| `--color-sidebar-dark` | `--barra-lateral` | `#0f172a` |
| `--color-sidebar-dark-soft` | `--barra-lateral-suave` | `#102a56` |
| `--color-panel-soft-staff` | `--panel-suave` | `#f8fafc` (sin superficie: cliente no tiene panel propio) |
| `--color-bg-staff` | `--fondo-staff` | `#f4f6fb` |
| `--color-text-staff` | `--texto-staff` | `#172033` |
| `--color-muted-staff` | `--atenuado-staff` | `#64748b` |
| `--color-border-staff` | `--borde-staff` | `#e5e7eb` |
| `--color-bg-client` | `--fondo-cliente` | `#F3F4F6` |
| `--color-text-client` | `--texto-cliente` | `#111827` |
| `--color-muted-client` | `--atenuado-cliente` | `#6B7280` |
| `--color-border-client` | `--borde-cliente` | `#E5E7EB` |
| `--font-family-staff` | `--fuente-staff` | `Inter, "Segoe UI", Arial, sans-serif` |
| `--font-family-client` | `--fuente-cliente` | `'Segoe UI', system-ui, sans-serif` |
| `--font-weight-regular` | `--peso-regular` | `400` |
| `--font-weight-semibold` | `--peso-semibold` | `600` |
| `--font-weight-bold` | `--peso-bold` | `700` |
| `--font-weight-extrabold` | `--peso-extrabold` | `800` |
| `--space-1` / `-3` / `-5` / `-7` / `-8` / `-9` | `--espacio-xs/sm/md/lg/xl/2xl` | `4/8/12/16/20/24px` |
| `--radius-sm` / `-md` / `-lg` / `-xl` | `--radio-sm/md/lg/xl` | `6/10/14/18px` |
| `--radius-xl-alt` | `--radio-2xl` | `20px` (el radio no-pill más grande de Fuel; encaja como siguiente escalón) |
| `--radius-pill` | `--radio-pill` | `999px` |
| `--shadow-modal` | `--sombra-sm` | `0 4px 20px rgba(0,0,0,.1)` |
| `--shadow-overlay` | `--sombra-md` | `0 8px 32px rgba(0,0,0,.18)` |
| `--shadow-panel` | `--sombra-lg` | `0 14px 35px rgba(15,23,42,.08)` |
| `--font-size-xs/sm/md/lg/xl/2xl` (staff) | `--texto-xs/sm/md/lg/xl/2xl-staff` | `11/12/15/16/17/21px` |
| `--font-size-client-xs/sm/md/lg/xl` | `--texto-xs/sm/md/lg/xl-cliente` | `0.8/0.82/0.95/1.1/1.6rem` |

**`--principal` y `--activo` — historia de la decisión:** en la Tanda 1 (renombrado puro) se
mapeó `--principal` al azul `#155eef` porque `admin.css` ya llamaba `--primary` a ese valor en
su propio código, y `--activo` al naranja `#E86A2C` porque se usa exactamente para el mismo rol
que Truck nombró `activo` (`.nav-item-active` en `admin.css`). Eso resultó ser el mapeo
equivocado: el objetivo real es que Truck y Fuel compartan la misma paleta, y en Truck
`--principal` es naranja. Corregido en la Tanda 2 (ver sección "Corrección: naranja de marca
unificado con Truck" más abajo) — `--principal` y `--activo` ahora son el mismo valor,
`#F16A30`.

**Escala de tamaños de texto con superficie — extensión del patrón de Truck:** Truck define
`texto-*` como escala plana porque solo tuvo panel admin. Fuel tiene dos sistemas de unidades
incompatibles (staff en `px`, cliente en `rem`), así que se extendió el mismo patrón
`-staff`/`-cliente` que ya usan los neutros de color a la escala de tamaños de texto
(`--texto-md-staff` / `--texto-md-cliente`). No está documentado todavía en el README de
Truck — es la primera vez que se necesita en la práctica.

**`--texto-2xl-cliente` no existe:** la escala cliente de Fuel no tiene un tamaño más grande
que `xl` (`1.6rem`) — no se inventó un valor para ese escalón.

### Extensiones nuevas (`color.json`) — mismo patrón de Truck, catálogo ampliado

Estos tokens tienen un rol único y real (no son variantes sueltas de un solo uso), y siguen
patrones de sufijo que Truck ya usa en otros tokens — pero no existen todavía en el catálogo
real de Truck:

| Nombre viejo (Tanda 0) | Nombre nuevo | Valor | Patrón que sigue |
|---|---|---|---|
| `--color-brand-orange-dark` | `--activo-oscuro` | `#C45520` | igual que `principal-oscuro` |
| `--color-danger-bg-upper` | `--fondo-peligro-suave` | `#FEF2F2` | igual que `fondo-naranja-suave` de Truck |
| `--color-success-bg-upper` | `--fondo-exito-suave` | `#F0FDF4` | ídem |
| `--color-warning-bg-upper` | `--fondo-aviso-suave` | `#FEF9C3` | ídem — agregado por consistencia con danger/success/info aunque no estaba en la propuesta inicial |
| `--color-info-bg-alt` | `--fondo-info-suave` | `#EFF6FF` | ídem |
| `--color-success-hover-upper` | `--exito-oscuro` | `#15803D` | igual que `principal-oscuro` |
| `--color-danger-text-upper` | `--texto-sobre-peligro` | `#991B1B` | igual que `texto-sobre-aviso` de Truck |
| `--color-success-text` | `--texto-sobre-exito` | `#166534` | ídem |
| `--color-warning-text-upper` | `--texto-sobre-aviso` | `#92400E` | **mismo nombre exacto que Truck** — valor propio de Fuel (`#92400E`, no el `#7a5800` de Truck: nombres compartidos, valores locales) |
| `--color-info-text-upper` | `--texto-sobre-info` | `#1E40AF` | igual que `texto-sobre-aviso` |

### Sin equivalente — quedan con su nombre `color-*` original (`color-sin-mapeo.json`)

~49 tokens: variantes de un solo uso capturadas tal cual en la Tanda 0 (fondos/textos
alternativos de alertas y badges sin rol compartido), duplicados de capitalización de los pares
que sí obtuvieron nombre compartido, y colores sin superficie ni rol semántico definido:
`color-danger-bg-alt-*`, `color-success-bg-alt/text-alt/bg-light/text-strong/bg-strong-*`,
`color-warning-bg-alt/text-alt/accent-1/accent-2/text-deep/amber`, `color-info-bg-upper/lower/
accent`, `color-generic-badge-*`, `color-role-cliente-*`, `color-gray-*` (9 tokens de soporte
para tablas/bordes genéricos), `color-landing-bg/text`. No se les inventó un nombre en español
porque no están en el vocabulario de Truck — traducirlos ahora sería crear catálogo compartido
que Truck no tiene. Candidatos a limpieza (fusión o baja) en una tanda futura, no en esta.

Igual criterio para tipografía/espaciado/radios: `font-family-mono`, `font-size-sm-alt/base/3xl/
4xl`, `font-size-client-sm-alt/base`, `font-weight-medium/semibold-alt/bold-alt/black`,
`space-2/4/6`, `radius-xs/sm-alt/md-alt/lg-alt` quedan con su nombre original — son valores
reales fuera de los 6 (o 4, o 5) escalones que define el vocabulario compartido. Viven en el
mismo archivo de su categoría (`typography.json`, `spacing.json`, `effects.json`) en vez de un
archivo aparte, porque siguen siendo tokens de esa categoría, solo fuera de la escala nombrada.

### Duplicados de capitalización — ninguno se borró

~15 pares de la Tanda 0 tienen el mismo color en mayúscula y minúscula de hex (ej.
`--color-danger-strong-upper: #DC2626` / `-lower: #dc2626`). La versión `-lower` es la que
recibe el nombre compartido (coincide con el case que ya usa el `:root` real de `admin.css`).
La versión `-upper` no se elimina — queda en `color-sin-mapeo.json` con su nombre y su
capitalización original intactos, documentada acá como duplicado de capitalización, candidato a
retirar en una tanda de limpieza futura.

**Nota de implementación:** todos los tokens de color (en las 3 archivos) están declarados como
`$type: "string"`, no `$type: "color"`. El transform group `css` de Style Dictionary
normaliza automáticamente los valores `$type: "color"` a hex en minúscula — eso habría
igualado sin querer los pares `-upper`/`-lower` (mismo string final) y habría cambiado la
capitalización literal de cada valor, violando "solo renombrar, no cambiar valores". Con
`$type: "string"` el pipeline no toca el valor en absoluto.

### `--fuente-landing` — único token nuevo con valor, no renombrado

Fuel no tenía una tipografía de landing distinta — `landing.html` ya usa el mismo stack que
cliente (`'Segoe UI', system-ui, sans-serif`, confirmado con grep). Por instrucción explícita
del pedido ("si le falta alguna, créala con el nombre igual y su valor propio"), se creó con
ese valor: mismo texto que `--fuente-cliente`, dos nombres para el mismo valor — no es un
error, es lo que ya existe hoy en el código.

`--fuente-base` (que sí existe en el catálogo real de Truck, idéntico a `fuente-cliente`) no se
creó en Fuel — no estaba en el pedido explícito de esta tanda.

## Corrección (Tanda 2): naranja de marca unificado con Truck

La Tanda 1 (arriba) fue un renombrado puro que preservó los valores que Fuel ya tenía. Al
revisarlo se detectó que el mapeo de `--principal` estaba mal: el objetivo real de este
proyecto es que Truck y Fuel compartan la misma paleta, y en Truck `--principal` es naranja
(`#f16a30`, el valor de la paleta de Adrián), no azul. La Tanda 1 había mapeado `--principal`
al azul `#155eef` (el `--primary` que ya usaba `admin.css`) siguiendo el nombre que Fuel ya
tenía internamente, sin cuestionar si ese era el color correcto para compartir con Truck.

**Cambio de valor (intencional, no un renombrado):**

| Token | Valor Tanda 1 | Valor Tanda 2 |
|---|---|---|
| `--principal` | `#155eef` (azul) | `#F16A30` (naranja, igual que Truck) |
| `--activo` | `#E86A2C` (naranja propio de Fuel) | `#F16A30` (unificado con `--principal`) |

`--activo` se unificó al mismo valor que `--principal` en la misma pasada — dejar `--principal`
en `#F16A30` (nuevo, sin uso real todavía) y `--activo` en `#E86A2C` (el naranja que Fuel ya usa
en todos lados) habría dejado dos naranjas casi idénticos conviviendo en el catálogo, exactamente
el tipo de casi-duplicado que este proyecto de tokens busca eliminar. Truck hace lo mismo:
`principal`/`activo`/`peligro` son el mismo `#f16a30` desde el rebrand de Adrián.

**Importante — esta corrección no cambia nada visible en la app todavía.** `tokens.css` sigue
sin estar enlazado a ningún layout (confirmado igual que en la Tanda 1: cero `<link>`, cero
`var(--principal)` en `templates/` o `static/`). `admin.css` sigue definiendo su propio
`--primary: #155eef` de forma completamente independiente. El cambio visual real (Fuel pasando
de interfaz azul a naranja en su superficie staff) va a ocurrir recién cuando una tanda futura
migre `admin.css`/templates a consumir estos tokens — no es parte de esta corrección.

### Inventario de usos de `#155eef` / `var(--primary)`, con rol — referencia para esa tanda futura

Grep completo sobre `static/` y `templates/`. Ningún uso es informativo (rol `--info`) — todos
son rol marca/acción (`--principal`). `--info` (`#0891b2`) ya se usa consistentemente aparte,
sin relación con este azul (dashboards, conciliación, badges "aprobada" en el portal cliente) y
no se toca.

| Uso | Ubicación | Rol |
|---|---|---|
| `--primary: #155eef` | `admin.css:7` | definición de la variable |
| `.eyebrow { color: var(--primary) }` | `admin.css:165` | etiqueta de marca sobre secciones |
| `.kpi-icon.primary { color: var(--primary) }` | `admin.css:209` | ícono de categoría "primaria" en KPI |
| `.btn-primary { background: var(--primary) }` | `admin.css:284` | botón de acción principal (CTA) |
| `.btn-soft` (color y hover-background) | `admin.css:293-294` | botón secundario suave, mismo rol de marca |
| `.form-control:focus { border-color: var(--primary) }` | `admin.css:316` | anillo de foco de inputs |
| `.form-control:focus { box-shadow: rgba(21,94,239,.12) }` | `admin.css:317` | halo de foco — mismo azul hardcodeado en rgba, sin variable; si se migra en el futuro debería recalcularse como el rgba de `--principal` nuevo, no solo cambiar el border |
| botón "volver" | `templates/404.html:12` | CTA en página de error, hardcodeado — fuera de alcance |
| botón "volver" | `templates/500.html:12` | ídem |

### `--principal-oscuro` y `--activo-oscuro`: sin cambios, a propósito

- `--principal-oscuro` sigue en `#0f3ea8` (azul). Truck tiene el mismo quirk documentado en su
  propio README: tras el rebrand de Adrián, `principal` pasó a naranja pero `principal-oscuro`
  se quedó azul (Adrián no definió un naranja oscuro). Dejar Fuel igual es la alineación más
  fiel con el estado real de Truck hoy, no un descuido.
- `--activo-oscuro` sigue en `#C45520`. A diferencia de `principal-oscuro`, este sí tiene uso
  real hoy en templates (`login.html`, `registro.html`, `tienda/index.html` — hover de botones
  naranja). Como esta corrección no toca templates, ese hover sigue siendo literalmente
  `#C45520` en la app — el token con ese valor es lo que refleja la realidad actual. Migrar el
  hover a un naranja oscuro derivado de `#F16A30` queda para la tanda que aplique estos tokens.

### `--peligro` no se toca

Truck colapsó `peligro` al mismo naranja que `principal` (Adrián no tiene un rojo propio).
Fuel no hace lo mismo acá: `--peligro` sigue en `#dc2626` (rojo real) porque esta corrección es
específicamente sobre `--principal`/`--activo`, no sobre extender el colapso de Adrián a los
demás roles semánticos.

## Enfoque: rename directo, sin capa de alias

Truck necesitó `color-legacy.json` (alias en inglés que resuelven a los nombres nuevos) porque
su `tokens.css` ya estaba consumido por 202 referencias `var()` reales en 30 archivos. **Fuel
no tiene ese problema**: se confirmó con grep que `tokens.css` de Fuel no está enlazado a
ningún layout y no hay una sola referencia `var(--color-...)`/`var(--font-...)`/
`var(--space-...)`/`var(--radius-...)`/`var(--shadow-...)` en todo `templates/` ni `static/`.
No había nada que una capa de alias pudiera proteger. Se renombró directo: el catálogo de Fuel
queda 100% en el vocabulario nuevo desde el día uno, sin la deuda de "nombres viejos a migrar
después" que sí tiene Truck.

## Cómo regenerar `static/css/tokens.css`

```bash
npm install        # solo la primera vez, o si cambió package.json
npm run tokens:build
```

Esto corre **en local**. Render no ejecuta Node — sigue sirviendo `static/css/tokens.css` como
archivo estático generado y comiteado. Después de regenerar, revisar el diff
(`git diff static/css/tokens.css`) antes de commitear.

**No editar `static/css/tokens.css` a mano.** Es el output del build — cualquier edición manual
se pierde en el próximo `npm run tokens:build`.

**No tocar `admin.css` ni ningún template desde esta carpeta.** `tokens/` solo define el
catálogo de variables disponibles; que un archivo empiece a usar `var(--principal)` en vez de
`#155eef` hardcodeado es una tanda de aplicación aparte, con su propio plan y verificación
visual — no forma parte de este renombrado.

## Qué NO cubre esta tanda

- No se aplicó ningún token a `admin.css` ni a ningún template — siguen con sus valores
  hardcodeados como antes. Esta tanda solo amplía el catálogo disponible en `tokens/`.
- No se adoptó la paleta de Adrián (el rediseño real de color que sí aplicó Truck) — Fuel sigue
  con sus valores actuales (el azul/naranja "pre-rebrand"). Es una tanda futura separada.
- No se fusionaron ni se borraron los ~49 tokens de `color-sin-mapeo.json` ni los duplicados de
  capitalización — quedan documentados como candidatos, la decisión de limpiarlos queda
  pendiente.
