# Reporte de Pruebas — 2026-06-29

## Commit verificado
`3e4890e` — fix: rol validation in usuarios crear/editar (string vs tuple comparison)

## Páginas probadas
- /login (admin, op_deposito, op_gasolinera, cliente_pma)
- /usuarios/crear (roles operario_deposito y operario_gasolinera)
- /usuarios/2/editar (rol cliente)
- /dashboard (op_deposito y op_gasolinera — verificación de sidebar)
- /portal/ (cliente_pma)

---

## Resultados por punto

| # | Verificación | Resultado | Detalle |
|---|-------------|-----------|---------|
| 1 | Crear usuario con rol `operario_deposito` | ✅ PASS | Redirige a `/usuarios/?ok=1` sin error |
| 2 | Crear usuario con rol `operario_gasolinera` | ✅ PASS | Redirige a `/usuarios/?ok=1` sin error |
| 3 | Editar usuario con rol `cliente` (sin cambiar rol) | ✅ PASS | Redirige a `/usuarios/?ok=1` sin error |
| 4 | Login `op_deposito@mercatoria.com` | ✅ PASS | Llega a Dashboard Depósito |
| 5 | Sidebar `operario_deposito` — solo OPERACIONES | ✅ PASS | Ve: Dashboard, Puertos, Depósitos, Transferencias, Salir |
| 6 | Login `op_gasolinera@mercatoria.com` | ✅ PASS | Llega a Dashboard Operario |
| 7 | Sidebar `operario_gasolinera` — solo OPERATIVA | ✅ PASS | Ve: Dashboard, Gasolineras, Turno del día, Habilitaciones, Despachos, Conciliación, Salir |
| 8 | Login `cliente_pma@mercatoria.com` / `Cliente2026!` | ✅ PASS | Redirige a `/portal/` — "Mi Resumen — Portal Cliente" |
| 9 | Portal cliente — nombre y KPIs cargan | ✅ PASS | Muestra "Programa Mundial de Alimentos", secciones del portal |

---

## Bug corregido

### ✅ RESUELTO — `rol not in _ROLES_LISTA` (string vs tuplas)

- **Archivo:** `blueprints/usuarios.py` líneas 84 y 166
- **Causa:** `_ROLES_LISTA` es lista de tuplas; `"cliente" not in [("cliente","Cliente"), ...]` siempre `True`
- **Fix:** `rol not in [r[0] for r in _ROLES_LISTA]`
- **Impacto anterior:** ningún usuario podía ser creado ni editado con ningún rol
- **Estado:** PASS en producción tras deploy `3e4890e`

---

## Bug 2 — Diagnóstico (no era código)

- **Síntoma reportado:** "cliente_pma no puede hacer login — credenciales incorrectas"
- **Resultado del test:** Login con `cliente_pma@mercatoria.com` / `Cliente2026!` PASA → redirige a `/portal/`
- **Conclusión:** No hay filtro por rol en el login (`app.py:82`). La causa más probable fue que el admin intentó resetear la contraseña vía editar → Bug 1 rechazaba el intento → confusión sobre cuál era la contraseña vigente
- **Contraseña del seed:** `Cliente2026!`

---

## Errores de consola

Sin errores de consola en ninguna de las páginas verificadas.

---

## Screenshots tomados

| Archivo | Pantalla |
|---------|----------|
| `fix_usuarios_listado.png` | Listado de usuarios post-creación (3 usuarios) |
| `fix_usuarios_listado_completo.png` | Listado completo con op_deposito y op_gasolinera creados |
| `fix_op_deposito_dashboard.png` | Dashboard Depósito — sidebar solo muestra OPERACIONES |
| `fix_op_gasolinera_dashboard.png` | Dashboard Operario — sidebar solo muestra OPERATIVA |
| `bug2_login_cliente_ok.png` | Portal cliente — login exitoso, nombre "Programa Mundial de Alimentos" |

---

## Correcciones aplicadas

- `blueprints/usuarios.py:84` — `rol not in _ROLES_LISTA` → `rol not in [r[0] for r in _ROLES_LISTA]`
- `blueprints/usuarios.py:166` — ídem

## Recomendaciones pendientes

- **Sin responsive móvil** — sidebar `width: 280px` fijo en `static/css/admin.css`, app inutilizable en < 768px (bug crítico sin resolver)
- **Selector depósito en puertos/isotanque** — query filtra `tipo_combustible` por igualdad exacta; puede no encontrar depósitos con multi-combustible (`"diesel,gasolina"`)
- **Base de datos efímera** — usar PostgreSQL en Render (actualmente SQLite en local/dev) para no perder datos entre redeployments
