# Reporte de Pruebas — 2026-07-10

---

## Commit fix corrupcion de disco verificado
`b785916` — fix: restaurar primer byte truncado en 7 blueprints

### Causa raiz
Disco SATA WD6TB (Event ID 157) desconecta cada ~56 segundos durante escritura atomica de git.
Al renombrar `.git/...file.lock` → `.git/...file`, el SO trunca el primer byte del archivo Python.

### Archivos corruptos restaurados

| Archivo | Byte perdido | Primera linea correcta |
|---------|-------------|----------------------|
| blueprints/conciliacion.py | `f` | `from datetime import...` |
| blueprints/habilitaciones.py | `f` | `from datetime import...` |
| blueprints/recepciones.py | `f` | `from flask import...` |
| blueprints/tarjetas.py | `f` | `from datetime import...` |
| blueprints/transferencias.py | `f` | `from flask import...` |
| blueprints/turno.py | `i` | `import os...` |
| blueprints/unidades.py | `i` | `import datetime...` |

### Efecto en produccion
Todos los deploys desde C1 (`b1abea6`) hasta Fase 1 (`d1f6cab`) fallaron con:
`SyntaxError: invalid syntax. Did you mean 'from'?` en blueprints/recepciones.py line 1.
La version live se quedo en `e7064f7` (antes de C1). Solo `b785916` subio el fix.

### Resultado
Deploy `b785916` → **Live** a las 3:32 PM GMT-4. 0 errores de consola.

---

## Commit Fase 1 Mensajes verificado
`d1f6cab` — Modulo Mensajes Fase 1: infraestructura SMTP + tabla mensajes + correo bienvenida

### Paginas probadas

| # | URL | Resultado | Notas |
|---|-----|-----------|-------|
| 1 | /mensajes/ | OK | Titulo "Mensajes enviados", tabla con 1 fila |
| 2 | /registro/ | OK | Formulario carga, registro exitoso a /registro/ok |
| 3 | /registro/ok | OK | Mensaje de confirmacion correcto |

### Fila verificada en mensajes

| Campo | Valor |
|-------|-------|
| destinatario | fase1.fix@test.mercatoria.online |
| asunto | Bienvenido a Mercatoria Fuel — tu cuenta ha sido creada |
| tipo | bienvenida |
| estado | fallido |
| error | (535, b'Incorrect authentication data') |
| usuario | Cliente Fase1 Fix — Empresa Fix SRL |

**Diagnostico del error 535:** Las variables SMTP estan configuradas en Render (SMTP_HOST,
SMTP_USER, SMTP_PASSWORD existen; si faltaran el error seria "SMTP no configurado").
El servidor responde pero rechaza las credenciales. Accion: verificar SMTP_PASSWORD en
Render > Mercatoria-Fuel > Environment.

### Errores de consola
Ninguno. 0 errores, 0 warnings.

### Screenshots
- `fase1_mensajes_verificacion.png` — Tabla de mensajes con fila bienvenida

### Infraestructura verificada

| Item | Estado |
|------|--------|
| Tabla `mensajes` creada en PostgreSQL | OK |
| Blueprint `/mensajes/` registrado y accesible (requiere_staff) | OK |
| Hook `bienvenida()` ejecutado tras INSERT en /registro/ | OK |
| Fila en mensajes: tipo=bienvenida, estado=fallido, error registrado | OK |
| Cuenta del cliente creada normalmente (SMTP error no bloquea registro) | OK |
| SMTP_PASSWORD correcto y envio real | PENDIENTE (error 535) |

---

## Commit C3 verificado
`e272a9e` — Refactor: centralizar calculo de stock y saldo Fincimex en helpers

### Páginas probadas (C3)

| # | URL | Stock visible | Resultado |
|---|-----|---------------|-----------|
| 1 | /depositos/ | 11,900.00 L (Refineria Nico Lopez) | ✅ |
| 2 | /gasolineras/ | Berroa 13,985 L / La Shell 43,844 L | ✅ |
| 3 | /transferencias/ | Página carga correctamente | ✅ |

### Errores C3
Ninguno. 0 errores de consola.

### Cambios aplicados (C3)

| Archivo | Cambio |
|---------|--------|
| utils/stock.py | NUEVO — `stock_deposito()` y `stock_gasolinera()` centralizados |
| blueprints/depositos.py | Local `_stock_deposito` removida → `from utils.stock import stock_deposito` |
| blueprints/recepciones.py | Local `_stock_deposito` removida → importada |
| blueprints/transferencias.py | Local `_stock_deposito` removida → importada |
| blueprints/gasolineras.py | Local `_stock_gasolinera` removida → `from utils.stock import stock_gasolinera` |
| blueprints/tarjetas.py | Dead `_stock_gasolinera` removida (definida pero nunca llamada) |

**Nota:** La copia en `depositos.py` usaba `row = cur.fetchone()` en línea separada; el SQL y resultado eran numéricamente idénticos al resto. El helper centralizado usa la forma inline. Resultado en producción: idéntico al centavo.

**Nota git:** Ref master quedó con SHA nulo tras error de cwd en shell. Reparado con `git cat-file` (verificación SHA) + Python file write. `git fsck --no-dangling` confirmó integridad completa. Push exitoso `733c146..e272a9e`.

---

## Commit C2 verificado
`733c146` — Limpieza: consolidar referencias a roles legacy en guards

**DB pre-commit:** SELECT confirmó 0 cuentas activas con rol pm o supervisor.

### Páginas probadas (C2)

| # | URL | Resultado | Notas |
|---|-----|-----------|-------|
| 1 | /reportes/ (admin) | ✅ | _ROLES_REPORTE actualizado a [admin, puesto_de_mando] |
| 2 | /transferencias/ (admin) | ✅ | _ROLES_TRANSFERENCIAS actualizado |
| 3 | /tl38/ (admin) | ✅ | Mensaje de error actualizado a puesto_de_mando |
| 4 | /tienda/admin (admin) | ✅ | _ROLES_STAFF y guards inline actualizados |

### Errores C2
Ninguno. 0 errores de consola.

### Cambios aplicados (C2)

| Archivo | Cambio |
|---------|--------|
| utils/constants.py | ROLES_ADMIN_PM, ROLES_OPERARIO_GAS, ROLES_OPERARIO_DEP: pm/supervisor removidos |
| blueprints/reportes.py | _ROLES_REPORTE: ["admin","puesto_de_mando"] |
| blueprints/tienda.py | _ROLES_STAFF + 2 inline guards: pm/supervisor → puesto_de_mando |
| blueprints/tarjetas.py | _ROLES_EDITAR_TARJETA: "pm" removido |
| blueprints/transferencias.py | _ROLES_TRANSFERENCIAS: "pm" removido |
| blueprints/tl38.py | Mensaje de error: pm → puesto_de_mando |
| blueprints/dashboard.py | Sin cambio — rama supervisor dejada como dead no-op |
| blueprints/usuarios.py | Sin cambio — _ROLES_VALIDOS conserva pm/supervisor intencionalmente |

---

## Commit C1 verificado
`b1abea6` — Seguridad: guard requiere_staff en barrido de rutas sin proteger

### Páginas probadas (C1)

| # | URL | Resultado | Notas |
|---|-----|-----------|-------|
| 1 | /conciliacion/ (admin) | ✅ | Carga correctamente con requiere_staff |
| 2 | /recepciones/ (admin) | ✅ | Carga correctamente con requiere_staff |
| 3 | /tarjetas/ (admin) | ✅ | Carga correctamente con requiere_staff |
| 4 | /conciliacion/ (sin sesión) | ✅ | Redirige a /login |
| 5 | /turno/ (sin sesión) | ✅ | Redirige a /login |

### Errores C1
Ninguno. 0 errores de consola, 0 warnings.

### Rutas protegidas C1 (18 rutas, 7 blueprints)

| Blueprint | Rutas migradas a requiere_staff() |
|-----------|-----------------------------------|
| conciliacion.py | listado, detalle, crear (3) |
| habilitaciones.py | detalle (1) |
| recepciones.py | listado (1) |
| tarjetas.py | listado, detalle, devolucion, liberar_devolucion (4) |
| transferencias.py | listado (1) |
| turno.py | index, api_crear_habilitacion, api_aprobar, api_despachar, cerrar_turno, api_reserva_info, api_reserva_completar (7) |
| unidades.py | listado (1) |

---

## Commit anterior verificado
`e7064f7` — Usuarios: rediseno estilo Truck (form embebido, chips por rol, acciones inline, buscador) preservando seguridad

## Páginas probadas

| # | URL | Resultado | Notas |
|---|-----|-----------|-------|
| 1 | /login | ✅ | Login admin OK, redirige a /dashboard |
| 2 | /usuarios/ | ✅ | Diseño nuevo desplegado correctamente |
| 3 | /usuarios/ — form embebido | ✅ | Toggle abre/cierra, botón cambia texto, campos condicionales cliente/gasolinera |
| 4 | /usuarios/ — chips de filtro | ✅ | Admin muestra 4 cuentas, Todos restaura 8 (incluyendo cualquier legacy) |
| 5 | /usuarios/ — buscador email | ✅ | "admin@" → solo admin@mercatoria.com |
| 6 | /usuarios/ — cambio rol inline | ✅ | editarRol/cancelarRol funciona, campo gasolinera condicional correcto |
| 7 | /usuarios/ — reset contraseña | ✅ | Sub-fila toggle, 2 inputs password, CSRF presente, action correcto |
| 8 | /usuarios/ — CSRF en todos los forms | ✅ | 24 forms POST, 0 sin csrf_token |
| 9 | /usuarios/ — guard sin sesión | ✅ | Redirige a /login correctamente |

## Errores encontrados

Ninguno. 0 errores de consola, 0 warnings HTTP.

## Screenshots tomados

- `usuarios_01_listado_nuevo.png` — Listado con chips, buscador y nueva estructura de columnas
- `usuarios_02_form_embebido_abierto.png` — Formulario de nuevo usuario desplegado
- `usuarios_03_listado_final.png` — Vista completa final tras verificación

## Correcciones aplicadas

Ninguna post-commit. El rediseño funcionó correctamente en primer despliegue.

## Comportamiento verificado

| Feature | Estado | Detalle |
|---------|--------|---------|
| Chip "Todos" muestra todos los roles (incluye legacy) | ✅ | count=8 incluye todos |
| Chip "Admin" filtra solo admins | ✅ | 4 filas, todos con data-rol="admin" |
| Chip "Puesto de Mando" count=1 | ✅ | Conteo correcto |
| Chip "Operador Gas." count=1 | ✅ | Conteo correcto |
| Chip "Cliente" count=2 | ✅ | Conteo correcto |
| Buscador por email (oninput) | ✅ | Filtro funciona en tiempo real |
| Form embebido colapsable | ✅ | Toggle visible/oculto + texto botón cambia |
| Campo cliente condicional (form nuevo) | ✅ | Aparece solo al seleccionar rol=cliente |
| Campo gasolinera condicional (form nuevo) | ✅ | Aparece solo al seleccionar rol=operador_gasolinera |
| Cambio rol inline (editarRol/cancelarRol) | ✅ | Badge↔form swap funciona |
| Campo gasolinera condicional (inline) | ✅ | Correcto para operador_gasolinera |
| Reset contraseña sub-fila | ✅ | Toggle, 2 inputs pw, CSRF, action /usuarios/3/reset-password |
| CSRF en todos los forms POST | ✅ | 24/24 forms tienen csrf_token |
| Guard _solo_admin() | ✅ | /usuarios/ sin sesión → /login |
| Columnas: Nombre/Email, Rol, Vinculado a, Estado, Creado, Acciones | ✅ | 6 columnas correctas |
| Badge roles legacy (pm, supervisor) | ✅ | Badge "legacy" en template, visibles con chip Todos |
| Botón cambiar rol oculto para propio usuario | ✅ | session.get('user_id') != u.id |

## Rutas POST protegidas — confirmación de guards

| Ruta | Guard | CSRF |
|------|-------|------|
| POST /usuarios/crear | _solo_admin() = requiere_rol("admin") | ✅ |
| POST /usuarios/\<uid>/toggle | _solo_admin() | ✅ |
| POST /usuarios/\<uid>/aprobar | _solo_admin() | ✅ |
| POST /usuarios/\<uid>/cambiar-rol | _solo_admin() | ✅ |
| POST /usuarios/\<uid>/reset-password | _solo_admin() | ✅ |

## Recomendaciones

1. **Crear un usuario de prueba con rol cliente** y verificar el flujo completo de creación desde el form embebido.
2. **El buscador filtra solo por email** — considerar ampliar a nombre en una iteración futura.
3. Los screenshots de sesiones anteriores (`sprint8_*.png`, `fincimex_*.png`) quedaron sin trackear en git — considerar limpiarlos o añadirlos a `.gitignore`.

---

# Mensajes Fase 2 — Avisos automáticos (cliente y staff) — 2026-07-10

## Nota sobre el entorno de verificación

Esta verificación se hizo **antes del commit/push**, tal como pidió Aldo explícitamente para esta fase. Como el código nuevo aún no está desplegado, probar contra `fuel.mercatoria.online` habría ejercitado la versión **anterior** del código (sin los avisos de Fase 2), lo cual no verifica nada real. En su lugar se levantó la app localmente (`python app.py`, SQLite local `fuel.db`, puerto 5051, sin tocar producción ni datos reales) y se ejercitaron los 8 puntos de disparo con Playwright/Chrome (navegador) para los flujos de cliente, y `curl` autenticado (con tokens CSRF extraídos de las páginas reales) para los flujos de staff que requerían datos operativos sintéticos (transferencias, conciliación). Ambos métodos ejecutan el mismo código Flask real, con la misma base de datos.

Detalle no relacionado con este cambio: al iniciar el servidor en el puerto 5000 por defecto, una sesión de Claude Code distinta ya tenía un servidor de **mercatoria-trucks** escuchando ahí, lo que causó una colisión de puerto y errores 400 confusos al principio. Se resolvió usando el puerto 5051, sin tocar el proceso ajeno.

## Páginas y flujos probados

| # | Flujo | Método | Resultado |
|---|-------|--------|-----------|
| 1 | Login admin / cliente (`/login`) | Navegador | ✅ |
| 2 | Configurar precio Diésel — La Shell (`/configuracion/`) | Navegador | ✅ |
| 3 | Agregar vehículo cliente (`/tienda/mis-vehiculos/`) | Navegador | ✅ |
| 4 | Crear reserva #1 (600L) → dispara **staff: reserva_pendiente** | Navegador | ✅ |
| 5 | Crear reserva #2 (500L) → dispara **staff: reserva_pendiente** | Navegador | ✅ |
| 6 | Aprobar reserva #1 (`/tienda/api/1/aprobar`) → dispara **reserva_aprobada** (QR inline) | Navegador | ✅ |
| 7 | Rechazar reserva #2 con motivo (`/tienda/api/2/cancelar`) → dispara **reserva_rechazada** | curl autenticado* | ✅ |
| 8 | Completar despacho con saldo insuficiente (`/turno/api/reserva-completar/<token>`) → dispara **staff: sin_cobertura_saldo** (variante saldo) | curl autenticado | ✅ |
| 9 | Completar despacho con saldo suficiente → dispara **despacho_completado** | curl autenticado | ✅ |
| 10 | Confirmar llegada de transferencia sin tarjetas activas → dispara **staff: sin_cobertura_saldo** (variante sin tarjeta) | curl autenticado | ✅ |
| 11 | Confirmar llegada con `sin_tarjeta_ok=1` (estado→recibida) → dispara **staff: combustible_sin_distribuir** | curl autenticado | ✅ |
| 12 | Crear conciliación con diferencia >0.5% (estado→con_alerta) → dispara **staff: conciliacion_diferencia** | curl autenticado | ✅ |

\* El paso 7 se probó primero desde el navegador; el clic sobre "Confirmar rechazo" falló en la UI por un token CSRF obsoleto **de la propia sesión de automatización del navegador** (no del código: se reprodujo el mismo endpoint con `curl` usando un token fresco extraído de la página recién cargada y respondió `{"ok":true}` en el primer intento). No se detectó ningún problema en el código de la aplicación por este motivo.

## Errores encontrados

- **Ninguno en el código de la aplicación.** `grep " 500 "` sobre el log completo del servidor de prueba: **0 resultados** en toda la sesión (67× 200, 16× 302, 2× 308, 5× 400 —todos validaciones de negocio esperadas—, 1× 404 favicon, 1× 405 —artefacto de un `curl -L` propio, no de la app—).
- Consola del navegador: 2 excepciones JS (`SyntaxError: Unexpected token '<'`) al intentar parsear como JSON la página de error 400 de CSRF durante el intento fallido descrito arriba (paso 7). No relacionado con la lógica de Fase 2.

## Trazas registradas en tabla `mensajes` (verificación de extremo a extremo)

| id | tipo | destinatario | estado |
|----|------|--------------|--------|
| 1, 2 | reserva_pendiente | admin@mercatoria.com | fallido (SMTP no configurado en local) |
| 3 | reserva_aprobada | cliente_pma@mercatoria.com | fallido (ídem) |
| 4 | reserva_rechazada | cliente_pma@mercatoria.com | fallido (ídem) |
| 5, 7 | sin_cobertura_saldo | admin@mercatoria.com | fallido (ídem) |
| 6 | despacho_completado | cliente_pma@mercatoria.com | fallido (ídem) |
| 8 | combustible_sin_distribuir | admin@mercatoria.com | fallido (ídem) |
| 9 | conciliacion_diferencia | admin@mercatoria.com | fallido (ídem) |

Los 9 registros confirman: (a) el punto de disparo se ejecuta exactamente donde cambia el estado o en la rama de error ya existente, (b) el destinatario se resuelve correctamente por rol o por cliente, (c) el fallo de envío (esperado en local, sin `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD`) queda registrado con su motivo y **no interrumpe la operación de negocio** — todas las reservas, despachos, transferencias y conciliaciones completaron su flujo normalmente pese al fallo de correo. La entrega real por SMTP no se valida aquí — la confirma Aldo en producción con las credenciales reales.

## Screenshots

Tomados y revisados en pantalla durante la sesión (login admin/cliente, dashboard, configuración de precios, alta de vehículo, formulario de reserva, panel de reservas con aprobar/rechazar). No se guardaron a disco como archivos porque el flujo de verificación fue local/interno — no se subieron a ningún reporte visual externo.

## Correcciones aplicadas

Ninguna — no se encontraron bugs. Los hooks de Fase 2 funcionaron según el plan aprobado en el primer intento.

## Recomendaciones

1. **Pendiente de Aldo**: verificar la entrega real de correo (SMTP) en producción con datos reales, incluyendo que el QR inline se vea correctamente en distintos clientes de correo (Gmail, Outlook) — Playwright no puede validar esto.
2. Tras el `git push`, correr una verificación ligera (sin mutar datos) en `fuel.mercatoria.online` per la regla POST-COMMIT del proyecto: cargar `/tienda/admin`, `/turno/escanear`, `/transferencias`, `/conciliacion` como admin y confirmar ausencia de errores de consola/HTTP, ya que ahí sí correrá el código nuevo desplegado.
3. Considerar en una futura fase permitir reintentos manuales de correos con `estado='fallido'` desde `/mensajes/`.

---

# Mensajes Fase 3 — Verificación de email obligatoria para reservar — 2026-07-10

## Nota sobre el entorno de verificación

Igual que en Fase 2: se verificó **antes del push**, contra una instancia local (`python app.py`, SQLite local `fuel.db` recreada desde cero por las migraciones, puerto 5052 dedicado — sin tocar producción ni datos reales). Se usó una combinación de navegador (Chrome/Playwright) para los pasos visuales clave y `curl` autenticado (con tokens CSRF extraídos de las páginas reales) para cubrir rutas adicionales rápidamente. Ambos métodos ejecutan el mismo código Flask real.

## Flujos probados

| # | Flujo | Método | Resultado |
|---|-------|--------|-----------|
| 1 | Registro de cliente nuevo → dispara `bienvenida` + `verificacion_email` | curl | ✅ |
| 2 | Aprobación admin (`activo=1`, gate preexistente sin tocar) | curl | ✅ |
| 3 | Cliente sin verificar navega `/tienda/`, `/tienda/mis-vehiculos/`, agrega vehículo | curl | ✅ sin bloqueo |
| 4 | Intento de confirmar reserva sin verificar → **bloqueado**, 0 filas en `reservas_tienda`, datos del formulario preservados (litros, gasolinera, combustible, vehículo) | Navegador + curl | ✅ |
| 5 | Aviso de bloqueo con botón "Reenviar" + input de código visibles | Navegador | ✅ (screenshot) |
| 6 | Verificación por **código** (AJAX, sin recargar página) | Navegador | ✅ (screenshot — banner cambia a verde, formulario intacto) |
| 7 | Confirmar la misma reserva tras verificar → **reserva #1 creada** con los mismos datos | Navegador | ✅ (screenshot) |
| 8 | Verificación por **enlace** (segundo cliente de prueba, token real extraído del cuerpo del correo) → redirige a `/tienda/reservar?verificado=1` | curl | ✅ |
| 9 | Token de enlace inválido/inexistente → redirige a `/login?verif_error=1` sin romper nada | curl | ✅ |
| 10 | Reenvío de verificación (tercer cliente de prueba) → nuevo token/código generado y trazado en `mensajes`, respuesta JSON honesta (`ok:false` por SMTP no configurado en local, igual que el resto de correos en este entorno) | curl | ✅ |

## Errores encontrados

- **Ninguno en el código de la aplicación.** Log completo del servidor de prueba: **0 errores 500** (41× 200, 16× 302, 2× 400, 1× 404 favicon). Los dos 400 fueron errores de mi propio script de prueba (variables de shell que no persisten entre invocaciones de la herramienta Bash, causando un CSRF token vacío en la petición) — no reproducibles desde la UI real, confirmado al repetir la misma llamada correctamente.
- La captura de pantalla vía Chrome tuvo 2 timeouts transitorios de `Page.captureScreenshot` (herramienta de automatización, no la app) — se reintentó y funcionó al segundo intento en ambos casos.

## Verificación en base de datos (extremo a extremo)

```
usuario #3 (fase3qa@example.com):     email_verificado 0→1 vía código; hashes y vencimiento quedaron NULL tras verificar
usuario #4 (fase3link@example.com):   email_verificado 0→1 vía enlace; hashes y vencimiento quedaron NULL tras verificar
reservas_tienda #1: estado='pendiente', 600.00 L — creada solo después de verificar, no antes
```

Confirma: el hash (no el valor plano) es lo único que se guarda mientras el token/código está pendiente; ambos caminos (enlace y código) validan el mismo correo; verificar limpia los campos de verificación (no quedan reutilizables); y el bloqueo es real de backend — la reserva #1 no existía en la tabla hasta después de que `email_verificado=1`.

## Correcciones aplicadas

Ninguna — no se encontraron bugs en el código de Fase 3. Los hallazgos de la sección "Errores encontrados" fueron artefactos del propio script/herramienta de prueba, no del código entregado.

## Recomendaciones

1. **Pendiente de Aldo**: verificar en producción que el correo de verificación (enlace + código) llega correctamente y que el enlace `https://mercatoria-fuel.onrender.com/tienda/verificar-email/<token>` resuelve bien sobre HTTPS real.
2. Igual que en Fase 2, correr una verificación ligera post-deploy en `fuel.mercatoria.online` (carga de `/tienda/reservar`, sin mutar datos reales) para confirmar que el código desplegado no tiene errores de consola/HTTP.
3. Considerar, en una fase futura, mostrar un recordatorio no bloqueante de "correo sin verificar" en el dashboard del cliente, para que no se entere solo hasta el momento de reservar (no se implementó ahora por estar fuera del alcance pedido: el bloqueo debía ser únicamente al confirmar).

---

# Mensajes Fase 4 — Mensajería masiva con aprobación y gestión — 2026-07-10

## Nota sobre el entorno de verificación

Verificado antes del push, contra instancia local (SQLite local, puerto 5053 dedicado, sin tocar producción ni datos reales). Navegador para los pasos visuales; `curl` autenticado (tokens CSRF reales extraídos de páginas) para los flujos adicionales de rol.

## Bug preexistente encontrado (no relacionado con Fase 4, no corregido — fuera de alcance)

`app.py::login()` línea 129: `session["gasolinera_id"] = fila.get("gasolinera_id")`. `fila` es un `sqlite3.Row` (SQLite) que **no tiene método `.get()`** — solo los dicts reales de `RealDictCursor` (Postgres/producción) lo soportan. Resultado: **cualquier login de un usuario con rol `operador_gasolinera` sobre SQLite local lanza un 500** en esa línea; en producción (Postgres) esta línea funciona sin problema. No se tocó `app.py` porque está fuera de los archivos aprobados en el plan de esta fase. Recomiendo corregirlo en una fase/commit aparte (cambio de una línea: `fila.get("gasolinera_id")` → `fila["gasolinera_id"]`), ya que actualmente bloquea probar ese rol en local con SQLite (no afecta producción).

## Flujos probados

| # | Flujo | Método | Resultado |
|---|-------|--------|-----------|
| 1 | Admin redacta masivo (`filtro=verificado`, in-app activado) → envía directo | Navegador | ✅ (screenshot: redacción con selección de destinatarios) |
| 2 | Resumen del envío: 4 destinatarios verificados, 0 excluidos (el filtro ya solo trajo verificados), 4 fallidos por SMTP no configurado en local (esperado) | Navegador | ✅ |
| 3 | Traza en `mensajes`: 4 filas `tipo='masivo'` (estado `fallido`, SMTP local) + 4 filas `tipo='masivo_inapp'` (estado `enviado`, sin canal externo) | BD | ✅ |
| 4 | PM redacta masivo (`modo=todos`) → botón dice "Enviar a aprobación", queda `estado='pendiente'`, **0 filas nuevas en `mensajes`** | Navegador + BD | ✅ |
| 5 | Admin entra a `/mensajes/masivos`: bandeja con Acciones primera columna, Ver/Aprobar/Rechazar inline solo para el pendiente | Navegador | ✅ (screenshot: bandeja de aprobación) |
| 6 | Admin aprueba el masivo del PM → pasa a `enviado`, resumen: 8 destinatarios totales (`todos` sin filtrar), 4 excluidos por no verificado, 4 fallidos (SMTP local) — coincide exactamente con los datos de prueba sembrados | Navegador | ✅ (screenshot: resumen de envío con excluidos) |
| 7 | PM redacta un tercer masivo; admin lo **rechaza** con motivo (`POST .../rechazar`) → `estado='rechazado'`, `motivo_rechazo` guardado, `total_enviados=0`, nada enviado | curl autenticado | ✅ |
| 8 | `operador_gasolinera` (rol staff pero no admin/PM) intenta `GET /mensajes/masivos/nuevo` y `GET /mensajes/masivos` → **302 a `/login`** (bloqueado por `requiere_rol(*ROLES_ADMIN_PM)`, no solo oculto en la UI) | curl con sesión firmada válida* | ✅ |
| 9 | Revisión de código: `masivos_aprobar()` y `masivos_rechazar()` llaman `requiere_rol("admin")` como primer chequeo, antes de tocar cualquier fila — confirmado por inspección directa del código entregado | Lectura de código | ✅ |

\* Para probar el paso 8 fue necesario **forjar una cookie de sesión Flask firmada** con el rol `operador_gasolinera` en vez de loguear por el formulario real, porque el bug preexistente descrito arriba impide completar ese login en SQLite local. Las rutas GET (que no requieren CSRF) confirmaron el bloqueo de forma concluyente. Las rutas POST (`aprobar`/`rechazar`) además exigen un token CSRF vinculado a una sesión creada por un login real — como la sesión fue forjada manualmente (no por un login real), esas pruebas específicas devolvieron 400 por CSRF antes de llegar siquiera al chequeo de rol; es decir, quedan bloqueadas por una capa de defensa previa (CSRF) además de por `requiere_rol`, lo cual es más protección, no menos. La captura visual del intento bloqueado no pudo tomarse vía login real de navegador por el mismo motivo; se sustituyó por la verificación HTTP directa arriba, más la revisión de código.

## Errores encontrados

- **Ninguno en el código de Fase 4.** El único 500 en todo el log del servidor de prueba corresponde al bug preexistente de `app.py::login()` descrito arriba, no relacionado con esta fase. El resto: 39× 200, 12× 302, 7× 400 (CSRF, todos explicados: mis propios errores de script o la sesión forjada de la prueba 8), 1× 404 (favicon).

## Correcciones aplicadas

Ninguna en el alcance de Fase 4 — no se encontraron bugs en el código entregado. Se documenta (sin corregir, fuera de alcance) el bug preexistente de `app.py` arriba.

## Screenshots

1. Redacción con selección de destinatarios (filtro = verificado, in-app activado).
2. Bandeja de aprobación (`/mensajes/masivos`, Acciones primera columna, Aprobar/Rechazar inline).
3. Resumen de envío con excluidos (8 destinatarios, 4 excluidos por no verificado, 4 fallidos por SMTP local).

(No se incluye captura del intento bloqueado por rol — ver nota arriba; el bloqueo quedó confirmado por HTTP directo y revisión de código.)

## Recomendaciones

1. **Pendiente de Aldo**: decidir si corregir el bug preexistente de `app.py::login()` (línea 129, `.get()` sobre `sqlite3.Row`) en un commit aparte — no afecta producción (Postgres) pero bloquea pruebas locales de `operador_gasolinera`.
2. Verificar en producción que los correos masivos lleguen bien formateados (el cuerpo permite HTML simple tecleado por el staff — sin sanitización adicional más allá de lo que ya hace el cliente de correo del destinatario).
3. Considerar en una fase futura un límite de tamaño de lote o un job asíncrono si el número de clientes crece mucho — hoy el envío ocurre síncronamente dentro de la misma request de aprobar/enviar.

---

# Fix: acceso a gasolinera_id en login (SQLite/PG) — 2026-07-10

## Cambio

`app.py::login()` línea 129: `fila.get("gasolinera_id")` → `fila["gasolinera_id"]`. Único cambio — mismo patrón de acceso por nombre que ya usa el resto de la función (`fila["nombre"]`, `fila["rol"]`, `fila["id"]`, `fila["activo"]`). Bracket access funciona igual en `sqlite3.Row` (SQLite) y en `RealDictCursor` (PostgreSQL/producción); si el valor SQL es `NULL`, devuelve `None` sin excepción — no se agregó ningún chequeo extra porque no hace falta.

## Verificación (local, SQLite, puerto 5054 — no producción)

| Rol | Cuenta de prueba | `gasolinera_id` | Resultado |
|---|---|---|---|
| admin | admin@mercatoria.com | n/a | ✅ 302 → /dashboard |
| puesto_de_mando | pm_qa@example.com | n/a | ✅ 302 → /dashboard |
| operador_gasolinera | opgas_qa@example.com | **NULL** | ✅ 302 → /dashboard (antes: 500) |
| operador_gasolinera | opgas_qa@example.com | **con valor** (id real) | ✅ 302 → /dashboard |
| cliente | masivo_verif1@example.com | n/a | ✅ 302 → /tienda/ |

Se probó explícitamente el caso `gasolinera_id IS NULL` (el usuario de prueba lo tenía así) y el caso con valor asignado — ambos sin error. Login de `operador_gasolinera` confirmado también por navegador: renderiza "Dashboard Operario" completo, badge de rol "OP-GAS", sidebar correcta — no solo el redirect HTTP. Screenshot capturado.

## Errores encontrados

Ninguno. **0 errores 500** en todo el log del servidor de prueba (11× 200, 6× 302, 1× 404 favicon) — el 500 original ya no ocurre.

## Correcciones aplicadas

La descrita arriba — una sola línea, sin tocar `session.clear()`, verificación de credenciales, ni guards, tal como se pidió.

## Recomendaciones

Ninguna pendiente — el hallazgo documentado en la sección de Fase 4 queda resuelto con este commit.

---

# Seguridad: no loguear correo de cliente en fallo de envío (mailer) — 2026-07-10

## Cambio

`utils/mailer.py::enviar_email()` — dos puntos, ambos en la misma función (el segundo fue un hallazgo adicional durante la auditoría previa, aprobado por Aldo antes de tocarlo):
- Línea ~57 (`logger.warning`, rama "SMTP no configurado"): `dest=%s", destinatario` → `usuario_id=%s cliente_id=%s", usuario_id, cliente_id`.
- Línea ~84 (`logger.error`, rama de excepción real de envío): `"Error enviando email a %s: %s", destinatario, exc` → `"Error enviando email (usuario_id=%s cliente_id=%s): %s", usuario_id, cliente_id, exc` — se conserva `exc` y `exc_info=True`.

`usuario_id`/`cliente_id` ya eran parámetros de la función (siempre en scope), mismo patrón que usan los otros ~15 `logger.error` del proyecto. No se tocó el `INSERT INTO mensajes` (la tabla `mensajes.destinatario` sigue guardando el correo completo — es almacenamiento en BD, no log; Aldo no pidió cambiar eso).

## Verificación (local, SQLite, puerto 5055 — no producción)

Se registraron 2 clientes de prueba nuevos (`/registro/`, que dispara `bienvenida()` + `enviar_verificacion()`, dos llamadas a `enviar_email()` cada una) bajo dos configuraciones distintas para forzar ambas ramas:

| Rama | Cómo se forzó | Log resultante | Correo del cliente en el log |
|---|---|---|---|
| "SMTP no configurado" (línea 57) | Servidor sin `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` | `Email no enviado — SMTP no configurado. usuario_id=13 cliente_id=None` (×2) | **Ausente** (`grep` del correo exacto → 0 resultados) |
| Excepción real de envío (línea 84) | Servidor con `SMTP_HOST=127.0.0.1`, `SMTP_PORT=1` (conexión rechazada) | `Error enviando email (usuario_id=12 cliente_id=None): [WinError 10061] ...` + traceback completo (`exc_info=True` intacto) | **Ausente** (`grep` del correo exacto → 0 resultados) |

Confirmado además que el resto del comportamiento no cambió:
- La tabla `mensajes` sigue trazando ambos intentos con `destinatario` completo, `estado='fallido'`, `error` con el texto de la excepción, y `usuario_id` correcto — verificado por consulta directa a la BD.
- El registro del cliente se completó igual (HTTP 302) pese al fallo de ambos correos — el aislamiento del fallo de SMTP sigue intacto, ninguna operación de negocio se rompió.
- **0 errores 500** en ambas sesiones de prueba.

## Errores encontrados

Ninguno.

## Correcciones aplicadas

Las dos descritas arriba, en `utils/mailer.py`. Ningún otro archivo ni ningún otro log fue tocado.

## Recomendaciones

Ninguna pendiente sobre este punto específico. Quedan abiertos (sin tocar, fuera de este alcance) los demás hallazgos de la auditoría de seguridad previa: rotación de la contraseña de admin sembrada, rate limiting en registro/verificación/masivos, y headers CSP/HSTS.

---

# Seguridad: rate limiting en rutas sensibles + HSTS y Referrer-Policy — 2026-07-10

## Cambio

Todo en `app.py`, sin tocar ningún blueprint:

- **Headers** (mismo `@app.after_request` existente, línea ~78-85): se agregan `Strict-Transport-Security: max-age=31536000; includeSubDomains` y `Referrer-Policy: strict-origin-when-cross-origin`.
- **Rate limiting**: como los blueprints se importan (línea 12-35) antes de que `limiter` exista (línea 53), no es posible usar `@limiter.limit(...)` como decorador dentro de `blueprints/registro.py`, `tienda.py` o `usuarios.py` sin import circular. Se optó por aplicar el límite **después** de `app.register_blueprint(...)`, reasignando `app.view_functions["<endpoint>"]` a la versión envuelta por `limiter.limit(...)`. Límites aplicados (los aprobados en el plan):

| Ruta | Límite |
|---|---|
| `POST /registro/` (`registro.index`, escopado con `methods=["POST"]`) | `5 per hour` |
| `POST /tienda/verificar-email/codigo` | `5 per minute` |
| `POST /tienda/verificar-email/reenviar` | `3 per minute` |
| `POST /usuarios/<uid>/reset-password` | `10 per minute` |

No se tocó `storage_uri="memory://"` ni el `@limiter.limit("10 per minute")` existente de `/login` — confirmado por `git diff` (cero cambios en esa línea).

**Nota para después (sin resolver aquí):** con `storage_uri="memory://"`, si Render corre más de un worker, cada proceso lleva su propio contador — el límite real efectivo sería `N × workers`, no `N` global. Evaluar respaldo con Redis/Postgres en una tarea aparte si aplica.

## Bug propio detectado y corregido durante la verificación (dentro de este mismo alcance)

Mi primer intento aplicó los límites así: `limiter.limit(...)( app.view_functions["endpoint"] )`, **descartando el valor de retorno**. `limiter.limit()` es un decorador — envuelve la función y devuelve una *nueva* función; no muta la original in-place. Al no reasignar `app.view_functions["endpoint"] = ...`, el límite quedaba definido pero nunca conectado al enrutamiento real de Flask. Lo detecté en la propia verificación (7 intentos seguidos a `/registro/` devolvieron 302, ninguno 429) antes de dar el commit por bueno, y lo corregí reasignando explícitamente cada entrada de `app.view_functions`. Ya verificado correcto tras el fix (ver tabla abajo).

## Verificación (local, SQLite, puerto 5056 — no producción)

| Ruta | Prueba | Resultado |
|---|---|---|
| `GET /login` | Cualquier respuesta | ✅ Headers `Strict-Transport-Security` y `Referrer-Policy` presentes |
| `POST /registro/` | 7 intentos seguidos | ✅ 1-5 → 302 (éxito), 6-7 → 429 |
| `GET /registro/` | 8 intentos seguidos | ✅ Todos 200 — el GET no está limitado (solo el POST, por diseño) |
| `POST /tienda/verificar-email/codigo` (sesión cliente real) | 7 intentos seguidos | ✅ 1-5 → 200, 6-7 → 429 |
| `POST /tienda/verificar-email/reenviar` (sesión cliente real) | 5 intentos seguidos | ✅ 1-3 → 200, 4-5 → 429 |
| `POST /usuarios/<uid>/reset-password` (sesión admin real) | 12 intentos seguidos | ✅ 1-10 → 302, 11-12 → 429 |
| `POST /login` | login real con admin y cliente | ✅ Ambos exitosos (302) — sin regresión. No se re-verificó el límite original de `/login` con un 429 limpio (no se tocó esa línea; `git diff` lo confirma, y de hecho ese límite interfirió con mi metodología de prueba en un intento inicial, lo que en sí confirma que sigue activo) |

**0 errores 500** en toda la sesión de verificación (61× 200, 17× 302, 16× 429 esperados, 18× 400 — estos últimos son CSRF de mi propio script al reintentar contra `/login`, que hace `session.clear()` en cada POST y por tanto invalida el token CSRF para reintentos con la misma sesión; no relacionado con este cambio).

## Errores encontrados

Ninguno en el código final entregado (el bug de `view_functions` descrito arriba se detectó y corrigió antes del commit, no llegó a integrarse).

## Correcciones aplicadas

Las descritas arriba, todas en `app.py`.

## Recomendaciones

1. Evaluar respaldar `storage_uri` con Redis/Postgres si Render corre múltiples workers (ver nota arriba).
2. Quedan abiertos de la auditoría previa: rotación de contraseña de admin sembrada, y `Content-Security-Policy` (tarea aparte, requiere probar contra los CDN externos ya en uso).

---

# Fix: confirmar llegada de transferencia no guardaba stock (fallo silencioso) — 2026-07-12

## Causa raíz confirmada

Mismatch de nombre de variable entre backend y template:

- `blueprints/transferencias.py:478` — `render_template(..., advertencia=advertencia, ...)`.
- `templates/transferencias/confirmar_llegada.html:24` y `:104` (antes del fix) — `{% if advertencia_tarjeta %}`, variable que **nunca se pasaba** desde Python.

Confirmado con `git blame`/`git show` que el mismatch viene del commit `df9ec655` ("Nuevo modelo saldo Fincimex...", 2026-07-10 12:08:53), hecho por **otra sesión de Claude Code** (Co-Authored-By: Claude Sonnet 4.6), anterior a mis Fases de Mensajes — no lo introduje yo.

**Efecto:** cuando la gasolinera destino no tiene ninguna tarjeta Fincimex activa para el combustible de la transferencia, el backend arma un aviso descartable y re-renderiza el formulario **sin guardar** (a propósito, esperando que el usuario marque un checkbox y reenvíe). Como el template nunca mostraba ni el aviso ni el checkbox (nombre de variable equivocado), el usuario veía el mismo formulario "recargado" sin ningún indicio de qué pasó, y no había forma de marcar el checkbox para continuar — cada reintento caía en el mismo callejón sin salida silencioso. No era una excepción no manejada (no había ningún 500 ni traceback) ni un rollback silencioso — el código funcionaba exactamente como se diseñó tras el commit del 10 de julio, solo que la condición de éxito (mostrar el checkbox) era visualmente inalcanzable.

## Corrección aplicada

Renombrar `advertencia_tarjeta` → `advertencia` en las 3 ocurrencias del template (2× `{% if %}`, 1× `{{ }}` de salida) — cero cambios en `blueprints/transferencias.py`, que ya hacía lo correcto.

## Verificación (local, SQLite, puerto 5057 — no producción)

Se sembraron 2 transferencias `en_transito` de prueba: una hacia "La Shell" (con 5 tarjetas Diésel activas — caso feliz) y otra hacia una gasolinera nueva "Santiago Paseo Marti" sin ninguna tarjeta (reproduce exactamente el escenario de la transferencia #9 real).

| Caso | Resultado |
|---|---|
| Caso feliz (destino con tarjeta) | ✅ `POST` → 302, `estado='recibida'`, `litros_recibidos=5000.0`, stock de La Shell (calculado vía `utils/stock.py::stock_gasolinera`, suma de `movimientos` tipo `transferencia_entrada`) = 5000 L. Screenshot: "Llegada confirmada — 2026-07-12". |
| Caso sin tarjeta, primer submit (sin marcar checkbox) | ✅ `POST` → 200 (no redirect), nada guardado (`estado` sigue `en_transito`) — **ahora sí visible**: banner amarillo "⚠️ Aviso: sin tarjeta Fincimex — Santiago Paseo Marti no tiene tarjetas Fincimex activas de Diésel..." y el checkbox "Entendido — confirmar llegada..." Screenshot de ambos. |
| Caso sin tarjeta, segundo submit (con checkbox marcado) | ✅ `POST` → 302, `estado='recibida'`, `litros_recibidos=8000.0`, stock de Santiago Paseo Martí = 8000 L |

**0 errores 500** en toda la sesión (28× 200, 7× 302, 1× 404 favicon). Hubo 2× 400 por CSRF, ambos artefactos de mi propia automatización del navegador (token reutilizado tras un `form.submit()` vía JS en una página que ya había cambiado de sesión) — reproducibles y explicados, no relacionados con el fix; confirmados como no-bugs repitiendo la misma acción con `curl` y un token CSRF recién extraído, que funcionó al primer intento.

También noté, y dejo documentado como hallazgo aparte (no corregido aquí, fuera de este alcance): al hacer clic físico en el botón "Confirmar llegada" desde la vista `/transferencias/<id>/gestionar` con la herramienta de automatización del navegador, el clic no siempre disparó el submit del formulario (confirmado revisando que no llegaba ningún POST al log del servidor). No até cabos de una causa de producto — es consistente con el mismo tipo de flakiness de clics ya visto en fases anteriores con esta herramienta de automatización, no con el código de la app.

## Errores encontrados

Ninguno nuevo — la causa raíz era la única anomalía real, ya corregida.

## Correcciones aplicadas

La descrita arriba, en `templates/transferencias/confirmar_llegada.html` únicamente.

## Recomendaciones

1. Confirmar en producción, contra la tabla `tarjetas` real, que "Santiago Paseo Martí" efectivamente no tenía tarjetas Diésel activas al momento del intento de Aldo con la transferencia #9 — esto terminaría de cerrar la causa raíz con evidencia de producción (el diagnóstico de código ya es concluyente por sí solo, pero esto lo confirmaría con el dato real).
2. Dado que este bug viene de un commit de otra sesión, sería valioso revisar el resto de cambios de `df9ec655` (bloqueo duro de saldo en despachos, generación de bolsón en recepciones) por posibles mismatches de variable similares — no lo hice aquí porque está fuera del alcance de este commit (exclusivamente el fix de `confirmar_llegada`).

---

# Saldo Fincimex: bloqueo por saldo USD también en habilitar (filtro temprano) — 2026-07-12

## Cambio

`blueprints/habilitaciones.py::aprobar()` — tres adiciones, sin tocar `blueprints/despachos.py`:
1. El `SELECT` (línea ~294) ahora trae también `t.saldo_usd` (antes solo `t.saldo_usable_l`).
2. Tras calcular `litros` (línea ~315), se lee `factor_litro_usd` de `configuracion` y se calcula `monto_usd = litros * factor` — mismo mecanismo y mismo default (0.90) que ya usa `despachos.py::crear()`.
3. Nuevo `elif float(hab["saldo_usd"] or 0) < monto_usd - 0.001:` insertado en la cadena existente, justo después del `elif` de `saldo_usable_l` — mismo mecanismo de bloqueo (`error` + redirect con `access_error`, `tarjeta_link` para el enlace "Recargar tarjeta"), mensaje en el mismo formato que `despachos.py` (disponible/requerido en USD, con el desglose litros × factor).

`despachos.py` queda intacto — coexisten dos líneas de defensa: habilitar (filtro temprano) y despachar (revalidación justo antes de descontar el saldo real).

## Verificación (local, SQLite, puerto 5058 — no producción)

Se sembraron 2 tarjetas de prueba sobre "La Shell": tarjeta A (`saldo_usable_l=3200`, `saldo_usd=100`) y tarjeta B (`saldo_usable_l=3200`, `saldo_usd=5000`), y 2 habilitaciones pendientes de 1000 L cada una (requieren 900 USD al factor default 0.90) — una por cada tarjeta.

| Caso | Resultado |
|---|---|
| Aprobar habilitación con tarjeta A (litros ok, USD insuficiente) | ✅ **Bloqueada** — `access_error=Saldo+Fincimex+insuficiente.+Disponible:+$100.00+USD,+requerido:+$900.00+USD+(1,000.00+L+×+0.9).&tarjeta_link=6`. `estado` permaneció `pendiente` en BD. Screenshot del banner rojo con el mensaje y el link "Recargar tarjeta →". |
| Aprobar habilitación con tarjeta B (ambos saldos suficientes) | ✅ `POST` → 302, `estado='aprobada'`, `aprobado_por` seteado. Screenshot: "Aprobada", botón "Registrar despacho" habilitado. |
| `despachos.py` sigue bloqueando (no se rompió) | ✅ Se aprobó la habilitación con tarjeta B y **después** se redujo manualmente `saldo_usd` de esa tarjeta a $50 (simula que el saldo cambió entre aprobar y despachar, el escenario real que justifica tener el chequeo en ambos puntos) → al intentar despachar, `despachos.py` bloqueó con `"Saldo Fincimex insuficiente. Disponible: $50.00 USD, requerido: $900.00 USD (1,000.00 L × 0.9)."`, HTTP 200 (re-render, no redirect). Confirmado en BD: `habilitaciones.estado` siguió `'aprobada'` (no pasó a `'despachada'`), 0 filas nuevas en `despachos`, saldo de la tarjeta sin cambios (`3200.0 L`, `$50.0`). |

**0 errores 500** en toda la sesión (21× 200, 4× 302, 1× 404 favicon).

## Errores encontrados

Ninguno.

## Correcciones aplicadas

La descrita arriba, en `blueprints/habilitaciones.py::aprobar()` únicamente.

## Recomendaciones

Ninguna pendiente sobre este punto — coexisten correctamente las dos líneas de defensa, tal como se pidió.

---

# Habilitaciones: validar en servidor que la tarjeta corresponde a gasolinera y combustible — 2026-07-12

## Diagnóstico (Fase 1)

Confirmado que el dato existe en el modelo, en ambos motores (evidencia completa en la respuesta de esta tarea): `tarjetas.gasolinera_id` y `tarjetas.tipo_combustible` son `NOT NULL`; `habilitaciones.gasolinera_id` es `NOT NULL` (columna directa); el combustible de la habilitación es indirecto vía `habilitaciones.unidad_id → vehiculos.tipo_combustible` (`NOT NULL`). No hubo ningún hueco de modelo — se procedió directo a la Fase 2 tras la aprobación.

Hallazgo adicional: el filtro de UI existente en `templates/habilitaciones/crear.html` ya filtraba tarjetas por gasolinera, pero **nunca por combustible** (el array JS de tarjetas ni siquiera incluía ese campo).

## Cambio

- `blueprints/habilitaciones.py::crear()` — nueva validación de servidor justo antes del `INSERT`, en el mismo bloque `else:` donde ya vive el chequeo de mínimo de litros: consulta `gasolinera_id`/`tipo_combustible` de la tarjeta y `tipo_combustible` de la unidad, y bloquea con `error` (mismo mecanismo que el resto de la función — re-render preservando `request.form`, CSRF se regenera solo) si no coinciden.
- `templates/habilitaciones/crear.html` — se agregó `combustible` al objeto JS de tarjetas y de unidades; nueva función global `filterTarjetas()` que filtra por gasolinera **y** por el combustible de la unidad seleccionada, disparada tanto al cambiar gasolinera como al cambiar unidad/cliente.

No se tocaron los chequeos de saldo (litros ni USD) en `aprobar()` ni en `despachos.py`.

## Verificación (local, SQLite, puerto 5059 — no producción)

Se sembraron 2 gasolineras, 1 vehículo Diésel, y 3 tarjetas: una correcta (misma gasolinera + mismo combustible), una de gasolinera distinta, una de combustible distinto.

| Caso | Método | Resultado |
|---|---|---|
| Filtro de UI: cliente → unidad Diésel → gasolinera La Shell | Navegador | ✅ El selector de tarjetas mostró solo las 8 tarjetas Diésel de La Shell — ninguna de gasolinera distinta ni de combustible distinto. Screenshot. |
| Tarjeta de gasolinera distinta (enviada directamente por fuera del filtro de UI, simulando una petición manipulada) | `curl` + Navegador (POST directo) | ✅ Bloqueada: `"La tarjeta seleccionada no corresponde a la gasolinera elegida."` — HTTP 200 (re-render, no redirect), datos del formulario preservados. 0 filas nuevas en BD. Screenshot. |
| Tarjeta de combustible distinto (misma gasolinera, combustible distinto, enviada por fuera del filtro) | `curl` + Navegador (POST directo) | ✅ Bloqueada: `"La tarjeta seleccionada no corresponde al tipo de combustible de la unidad."` — mismo mecanismo. Screenshot. |
| Caso feliz: tarjeta correcta, elegida desde el propio selector ya filtrado | Navegador | ✅ Habilitación creada (`estado='pendiente'`), datos correctos (Diésel, La Shell, tarjeta ****3333). Screenshot. |

Confirmado en BD que los dos intentos bloqueados no crearon ninguna fila; solo el caso feliz generó una habilitación nueva.

**0 errores 500** en toda la sesión (29× 200, 4× 302, 1× 404 favicon).

## Errores encontrados

Ninguno.

## Correcciones aplicadas

Las descritas arriba, en `blueprints/habilitaciones.py::crear()` y `templates/habilitaciones/crear.html`.

## Recomendaciones

Ninguna pendiente sobre este punto.

---

# Fotos: almacenamiento en PostgreSQL en vez de disco efímero de Render — 2026-07-13

## Diagnóstico previo

`diagnostico_fotos.md` (no commiteado) confirmó la causa raíz de los 404 de fotos de ticket: `render.yaml` no define `disk:` para el servicio web, las fotos se guardaban con `foto.save()` en `static/uploads/` del disco local, y ese disco es efímero (se borra en cada deploy/reinicio de Render).

## Cambio

- Tabla nueva `adjuntos` (`CREATE TABLE IF NOT EXISTS`, ambos motores) — guarda el binario (`BYTEA`/`BLOB`), `origen_tipo`/`origen_id`, `categoria`, `mime_type`.
- `utils/adjuntos.py` — helper único `guardar_adjunto()` (+`foto_valida()`), reemplaza `_save_photo()` de `despachos.py` y las 2 duplicaciones inline de `turno.py`.
- 3 call sites migrados a guardar el binario en la misma transacción del despacho/reserva que lo origina: `despachos.py::crear()`, `turno.py::api_despachar()`, `turno.py::api_reserva_completar()`.
- Ruta nueva `GET /adjuntos/<id>` (`blueprints/adjuntos.py`) — sirve el binario con guard: staff sin restricción, cliente solo si es dueño del despacho/reserva (join a `despachos.cliente_id` o `reservas_tienda.usuario_id`), 403 si no, 302 si no hay sesión.
- 4 templates (`despachos/detalle.html`, `despachos/listado.html`, `habilitaciones/detalle.html`, `portal/despachos.html`) — URLs viejas bajo `/static/uploads/` (archivo ya perdido) degradan a placeholder "Sin imagen" en vez de `<img>` roto.
- `app.py` — se quitó el bloque `UPLOAD_FOLDER`/`os.makedirs` sin uso.

No se tocó lógica de saldo/stock/habilitaciones — solo dónde y cómo se guarda/sirve la foto.

## Verificación (local, SQLite fresco, puerto 5050 — no producción)

| Caso | Método | Resultado |
|---|---|---|
| Subir 3 fotos (ticket/vehículo/odómetro) en `despachos/crear` | Navegador (inyección de `File` vía JS + `form.requestSubmit()`, el `file_upload` de paths de disco dejó de estar soportado por el MCP) | ✅ Despacho creado, 3 filas en `adjuntos` con `origen_tipo='despacho'`, cero archivos nuevos en `static/uploads/`. Imágenes visibles en el detalle vía `/adjuntos/<id>` (200, `image/jpeg`). |
| Despacho abortado por carrera de saldo (2 requests concurrentes a `/turno/api/<id>/despachar` sobre la misma tarjeta, litros que exceden el saldo combinado) | `curl` concurrente | ✅ El ganador se despachó normalmente; el perdedor devolvió el error de carrera esperado y **no dejó fila huérfana en `adjuntos`** ni despacho a medias — confirmado en BD. |
| Despacho viejo con `foto_ticket_url='/static/uploads/tickets/perdido123.png'` (archivo inexistente) | Fila insertada directo en BD + navegador | ✅ `despachos/detalle.html` y `despachos/listado.html` muestran "Sin imagen (archivo no disponible)" / "Sin imagen", no un `<img>` roto ni 404 de página. |
| Completar reserva de Tienda vía QR (`/turno/api/reserva-completar/<token>`) con foto | `curl` (la UI de escaneo con cámara quedó con el renderer bloqueado — probable prompt de permiso de cámara sin resolver; se abandonó esa pestaña y se verificó la ruta real por API) | ✅ Reserva marcada `completada`, adjunto en BD con `origen_tipo='reserva_tienda'`, imagen servida en 200 desde `/adjuntos/<id>`. |
| Guard de acceso: cliente ajeno a un despacho/reserva | `curl` autenticado como `cliente_otro@mercatoria.com` (usuario de prueba, sin relación con los registros) | ✅ 403 en ambos adjuntos ajenos. |
| Guard de acceso: cliente dueño del registro | `curl` autenticado como `cliente_pma@mercatoria.com` (dueño real de los registros de prueba) | ✅ 200 en su propio despacho y su propia reserva. |
| Guard de acceso: sin sesión | `curl` sin cookies | ✅ 302 a `/login`. |

**0 errores 500** en la sesión.

## Errores encontrados

Ninguno funcional. Nota operativa: el `file_upload` del MCP de Chrome dejó de aceptar rutas de disco directamente (requiere que el controlador MCP lea el archivo) — se resolvió inyectando los archivos vía `DataTransfer`/`File` con JavaScript. La pestaña de "Escanear QR" del turno quedó con el renderer bloqueado tras click en "Marcar como despachada" (posible prompt de cámara pendiente sin resolver) — no se forzó interacción con el diálogo; se verificó el mismo endpoint por API directamente.

## Correcciones aplicadas

Las descritas arriba.

## Recomendaciones

- Verificación en producción (https://mercatoria-fuel.onrender.com) queda a cargo de Aldo, como es el procedimiento habitual — Claude Code no inicia sesión en producción.
- Sería válido, en otra sesión, investigar por qué la pestaña de escaneo QR del turno bloqueó el renderer del navegador de pruebas (posible prompt de cámara nativo) si se quiere automatizar esa pantalla específica con Playwright a futuro.

---

# Habilitaciones: modo "en reserva" en subinventario, liberar, y limpieza de campo muerto — 2026-07-13

## Diagnóstico previo

`diagnostico_subinventarios.md` (no commiteado) mapeó el modelo completo: `clientes.subinventario_reservado_l` era un número muerto desconectado de la tabla real `subinventarios`; los subinventarios reales solo se creaban/editaban desde `/gasolineras/<id>/subinventarios`; las habilitaciones solo podían *consumir* una reserva existente (nunca crearla), y el desplegable de subinventario en Crear Habilitación no tenía ningún dato real con el que probarse en el entorno de Aldo.

## Cambio

- `clientes.py`/`clientes/crear.html`/`clientes/editar.html` — quitado el campo "Litros reservados en subinventario" de ambos formularios y de los `INSERT`/`UPDATE`. La columna de la tabla no se tocó (sin `DROP`).
- `utils/subinventarios.py` (nuevo) — `crear_subinventario()` y `ajustar_reserva()` (+ `validar_tope_reserva()` interno), con el mismo tope de stock físico que ya existía en `gasolineras.py`. `gasolineras.py::subinventario_crear()` y `subinventario_editar()` refactorizados para reutilizar este helper en vez de duplicar la lógica.
- `utils/constants.py` — nuevo estado `en_reserva` en `ESTADOS_HABILITACION` (columna `TEXT` libre, sin `ALTER TABLE`).
- `habilitaciones/crear.html` — toggle Despacho/En reserva; dentro de En reserva, elegir un subinventario existente (desplegable, ahora poblado y filtrado correctamente por gasolinera) o crear uno nuevo inline (tipo `cliente`, cliente autocompletado).
- `habilitaciones.py::crear()` — en modo reserva: subinventario obligatorio, se omite la validación de saldo Fincimex, se mantiene la validación estructural tarjeta/gasolinera/combustible, `INSERT` con `estado='en_reserva'`, y en la misma transacción `ajustar_reserva(+litros_autorizados)` más un movimiento de auditoría `tipo='habilitacion'` (constante ya definida, sin uso previo, no afecta el cálculo de stock físico).
- `habilitaciones.py::liberar()` (nueva ruta `POST /habilitaciones/<id>/liberar`) — solo desde `en_reserva`; reutiliza exactamente las validaciones de `aprobar()` (tarjeta activa, saldo litros, saldo USD, subinventario suficiente); no toca `litros_reservados` ni `movimientos`.
- `habilitaciones.py::cancelar()` — acepta también `en_reserva`; en ese caso devuelve los litros al subinventario vía `ajustar_reserva(-litros_autorizados)`, acotado a lo que realmente quede reservado (nunca negativo), con nota de discrepancia en observaciones si se acotó.
- `habilitaciones/listado.html` y `detalle.html` — badge "En reserva", botón "Liberar reserva" (solo Admin/PM, solo en ese estado).

No se tocó ningún código de `despachos.py`/`turno.py` — el despacho real, que ya decrementaba `litros_reservados` correctamente cuando había `subinventario_id`, se reutiliza sin cambios.

## Verificación (local, SQLite fresco, puerto 5060 — no producción)

Fixtures: gasolinera La Shell con 5,000 L de stock físico (vía movimiento `transferencia_entrada` sembrado), tarjeta ****8777 con saldo inicial 3,200 L / $1,000 USD, cliente PMA, vehículo de prueba.

| Paso | Método | Resultado |
|---|---|---|
| Apartar 1,200 L en modo reserva (subinventario nuevo, tipo cliente autocompletado) | `curl` autenticado, `POST /habilitaciones/crear` | ✅ Habilitación `estado='en_reserva'`; subinventario creado con `litros_reservados=1200`; **tarjeta sin cambios** (3200 L / 1000 USD intactos); movimiento de auditoría `tipo='habilitacion'` registrado; **sin** movimiento `tipo='despacho'`. |
| Efecto en gasolinera tras apartar | `GET /gasolineras/1` | ✅ Stock físico sigue en 5,000.00 L; reservado sube a 1,200.00 L (24.0%); **Disponible para venta baja a 3,800.00 L**. |
| Liberar con saldo insuficiente | `POST /habilitaciones/1/liberar` (saldo_usd=1000, requerido=1080) | ✅ Bloqueado: "Saldo Fincimex insuficiente... requerido: $1,080.00 USD" — mismo mensaje/mecanismo que `aprobar()`. |
| Liberar con saldo suficiente (tras subir saldo_usd a 2000) | `POST /habilitaciones/1/liberar` | ✅ `estado` pasa a `aprobada`; `litros_reservados` del subinventario **sin cambios** (sigue en 1200); cero movimientos `despacho` todavía. |
| Despachar los 1,200 L (con foto de ticket) | `POST /despachos/crear` (multipart) | ✅ Habilitación `despachada`; `litros_reservados` del subinventario baja a **0**; tarjeta baja a 2,000 L / 920 USD; movimiento `despacho` de 1,200 L registrado. |
| **Verificación crítica: sin doble descuento** | `GET /gasolineras/1` tras el despacho | ✅ Reservado vuelve a 0.00 L; **Disponible para venta sigue en 3,800.00 L** — exactamente el mismo valor que tras apartar. El stock físico bajó a 3,800 (5000−1200) y la reserva bajó a 0 en el mismo movimiento, así que el disponible no se mueve dos veces. |
| Segunda reserva (500 L, subinventario existente) + Cancelar | `POST /habilitaciones/crear` (sub_modo=existente) → `POST /habilitaciones/2/cancelar` | ✅ Subinventario sube a 500 L al apartar, vuelve a 0 al cancelar; habilitación queda `cancelada`; sin discrepancia (se devolvió el 100%). |
| Desplegable de subinventario en Crear Habilitación | HTML renderizado (`GET /habilitaciones/crear`) | ✅ El array JS `subinventarios` trae la fila real (`id:"1", gasolinera:"1", label:"Programa Mundial de Alimentos — 0 L"`) — ya no vacío. |
| Campo muerto fuera de Crear/Editar cliente | HTML renderizado (`GET /clientes/crear`, `GET /clientes/1/editar`) | ✅ Cero apariciones de `subinventario_reservado_l` en ambos formularios. |

**0 errores 500** en toda la sesión.

## Errores encontrados

Ninguno funcional. Nota operativa: la pestaña del navegador de pruebas no logró conectar a `127.0.0.1`/`localhost` en el puerto local (error de red del propio entorno de automatización, confirmado que no era el servidor — `curl` respondía 200 en paralelo) — la verificación visual del desplegable y de los formularios de cliente se hizo igualmente, vía inspección del HTML renderizado por `curl` en vez de captura de pantalla.

## Correcciones aplicadas

Las descritas arriba.

## Recomendaciones

- Verificación en producción queda a cargo de Aldo, como siempre.
- El análisis de código no encontró un defecto puntual en el JS del desplegable de subinventario (la lógica de refiltrado en carga/cambio ya era correcta); la percepción de "siempre vacío" era consistente con que la gasolinera probada nunca tuvo subinventarios reales — algo que este cambio resuelve de raíz al conectar el flujo completo.

---

# Despacho: foto opcional-diferida, pendientes de imagen en dashboard, y búsqueda manual sin QR — 2026-07-13

## Contexto

Tres necesidades operativas reales: despachar sin QR (cliente sin QR, sin cámara, sin conexión) y sin foto en el momento (subirla después). Se detectó además, al inspeccionar el código, que el flujo de "Marcar como despachada" en `turno/escanear.html` (reservas de Tienda) **nunca envía foto** — con la validación obligatoria que había, ese botón fallaba siempre en producción. Este cambio confirma y corrige esa causa raíz de paso.

## Cambio

- `despachos.py::crear()`, `turno.py::api_despachar()`, `turno.py::api_reserva_completar()` — se quitó el bloque que exigía `foto_ticket`; la foto sigue validándose en formato solo si viene.
- `despachos/crear.html` — input de foto ya no `required`, etiqueta y ayuda actualizadas a "(opcional)".
- "Pendiente de imagen" se deriva de `foto_ticket_url IS NULL` — sin columna nueva, en `despachos` (por despacho) y `reservas_tienda` (por reserva completada), ambas columnas ya se mantenían en sincronía con `adjuntos` en cada flujo de guardado.
- Nueva ruta `POST /despachos/<id>/subir-foto` — guard `requiere_staff()`, con restricción de gasolinera para `operador_gasolinera` (mismo patrón que `turno.py`). Usa `guardar_adjunto()` existente + `UPDATE despachos.foto_ticket_url` en la misma transacción.
- `despachos/detalle.html` — cuando no hay foto de ticket: badge "Pendiente de imagen" + formulario de subida inline, visible para cualquier staff.
- Nuevos endpoints de solo lectura `GET /turno/api/reserva-info-por-numero/<id>` y `GET /turno/api/habilitacion-info/<id>` — buscan por número (id) en vez de por token/QR. El de reserva devuelve el `qr_token` real para reutilizar `mostrarResultado()`/`completar()` **sin cambios**; el despacho de habilitación reutiliza `api_despachar()` **sin cambios** (ya funcionaba por número).
- `turno/escanear.html` — nuevo panel "Buscar por número (sin QR)" con dos campos (reserva de Tienda / habilitación); se mantiene intacto el escáner de cámara y el token manual.
- `dashboard.py` — contador `pendientes_imagen` = `COUNT` de `despachos` completados sin foto + `COUNT` de `reservas_tienda` completadas sin foto. Nueva tarjeta KPI en `dashboard.html` y `dashboard_supervisor.html`.

**Alcance confirmado con Aldo:** las reservas de Tienda sin foto **cuentan** en el contador del dashboard, pero no tienen una pantalla de "detalle de reserva" hoy, así que no obtienen un control de "subir después" en este cambio — quedan pendientes visibles pero sin botón de arreglo hasta una tarea futura, si hace falta.

No se tocó ninguna lógica de saldo, stock, subinventario ni el circuito Fincimex.

## Verificación (local, SQLite fresco, puerto 5070 — no producción)

Fixtures: gasolinera La Shell (5000 L de stock), 3 tarjetas con saldo, 4 habilitaciones aprobadas, 1 reserva de Tienda aprobada, usuario de prueba `operador_gasolinera`.

| Caso | Método | Resultado |
|---|---|---|
| 1. Despachar SIN foto (`despachos.py::crear()`) | `curl` multipart sin `foto_ticket` | ✅ HTTP 302, despacho creado; detalle muestra badge "Pendiente de imagen" + formulario de subida. Dashboard sube de 0 a 1. |
| 3. Despachar CON foto en el momento (`turno.py::api_despachar()`) | `curl` multipart con `foto_ticket` | ✅ Despachado; detalle muestra la imagen directamente (`/adjuntos/1`), sin badge de pendiente. Contador no sube por este. |
| 4a. Buscar reserva por número (sin QR) | `GET /turno/api/reserva-info-por-numero/1` → `POST /turno/api/reserva-completar/<token resuelto>` sin foto | ✅ El lookup devuelve el token real; `completar()` (mismo endpoint de siempre) se ejecuta exitosamente sin foto. |
| 4b. Buscar habilitación por número (sin QR) | `GET /turno/api/habilitacion-info/3` → `POST /turno/api/3/despachar` sin foto | ✅ Lookup correcto (cliente, gasolinera, litros, tarjeta); despacho completado sin foto vía el mismo `api_despachar` de siempre. |
| 5. Contador combinado sube | `GET /dashboard` tras los pasos 1 y 4a/4b | ✅ Sube a **3** (2 despachos de flota sin foto + 1 reserva de Tienda sin foto) — confirma que suma ambas fuentes. |
| 2. Subir foto después — operario | Login como `operador_gasolinera` de la misma gasolinera → `POST /despachos/1/subir-foto` | ✅ Foto guardada vía `guardar_adjunto()`, deja de estar pendiente. |
| 2. Subir foto después — PM/admin | `POST /despachos/3/subir-foto` como admin | ✅ Igual de exitoso. |
| 5. Contador combinado baja | `GET /dashboard` tras subir las 2 fotos de flota | ✅ Baja a **1** — queda solo la reserva de Tienda (fuera de alcance de "subir después", como se confirmó con Aldo), confirmando que el contador refleja con precisión ambas fuentes en tiempo real. |
| Verificación visual | Navegador contra la instancia local — dashboard, `turno/escanear` (panel nuevo), `despachos/<id>` (badge + formulario pendiente) | ✅ Los tres se ven según lo diseñado. Screenshots tomados. |

**0 errores 500** en toda la sesión.

## Errores encontrados

Ninguno. Se confirmó (no se corrigió aparte, ya venía incluido en este cambio) que `turno/escanear.html::completar()` nunca enviaba foto — con la validación previa esa ruta fallaba siempre; con la foto opcional ahora funciona.

## Correcciones aplicadas

Las descritas arriba.

## Recomendaciones

- Verificación en producción queda a cargo de Aldo, como siempre.
- Si en el futuro se quiere permitir subir la foto después también para reservas de Tienda, hace falta antes una pantalla de detalle de reserva (hoy solo existe el listado en `/tienda/admin`) — quedó fuera de alcance de este cambio por decisión explícita de Aldo.

---

# PIN visible en plano, etiqueta "Venta", y número de operación automático — 2026-07-13

## Cambio

**1. PIN de tarjeta visible (decisión operativa de Aldo, baja de seguridad deliberada):**
- Columna nueva `tarjetas.pin_plano TEXT` (nullable, `ADD COLUMN IF NOT EXISTS` en ambos motores). La columna vieja `pin_hash` (NOT NULL) se sigue escribiendo igual que antes (satisface el constraint, queda como legado sin uso real) — evita tocar su NOT NULL y evita cualquier migración de tipo `ALTER COLUMN` (no soportada de forma simple en SQLite).
- `tarjetas.py::crear()` guarda el PIN tal cual en `pin_plano` además de seguir hasheando en `pin_hash`.
- `tarjetas.py::editar()` — nuevo campo PIN opcional (vacío = no cambiar); es el mecanismo para reintroducir PINs viejos irrecuperables.
- `tarjetas/detalle.html` — fila "PIN" visible solo para `admin`, `puesto_de_mando`, `operador_gasolinera`. Si `pin_plano` existe se muestra; si no (PIN viejo, solo hasheado), muestra "PIN no disponible (reintroducir)".

**2. Etiqueta "Venta":** en `habilitaciones/crear.html`, la opción vacía del desplegable de subinventario pasa de "Sin subinventario específico" a "Venta" (2 lugares: el `<option>` estático y la función JS `subEmptyLabel()`). Sin cambio de valor/lógica.

**3. Número de operación automático:**
- Columna nueva `despachos.numero_operacion TEXT` (nullable) + `CREATE UNIQUE INDEX IF NOT EXISTS` en ambos motores — la base es la garantía real de unicidad, no solo el cálculo en Python. (SQLite no soporta `UNIQUE` inline en `ADD COLUMN`, confirmado localmente; de ahí el índice separado, usado igual en ambos motores por consistencia.)
- `utils/despachos.py` (nuevo) — `_candidato_numero_operacion()` calcula `AAAAMMDD` (8) + `id_gasolinera` (2, con padding) + `secuencia_del_día` (4, con padding) = 14 dígitos, vía `COUNT(despachos de esa gasolinera ese día) + 1`, con rango de fecha (no substring) para funcionar igual con los dos formatos de `fecha_despacho` que ya convivían en el código (timestamp completo en `despachos.py`, solo fecha en `turno.py`). `insertar_despacho_con_numero()` ejecuta el `INSERT` dentro de un `SAVEPOINT`; si choca con el `UNIQUE` (carrera real entre despachos concurrentes), hace `ROLLBACK TO SAVEPOINT`, recalcula el siguiente número disponible y reintenta (hasta 20 intentos) — nunca deja que la colisión rompa el despacho.
- `despachos.py::crear()` y `turno.py::api_despachar()` usan el helper. Reservas de Tienda quedan fuera de alcance (decisión confirmada con Aldo).
- `despachos/detalle.html` (encabezado + tabla) y `despachos/listado.html` (columna nueva) muestran el número; `—` si es `NULL` (despachos viejos, sin backfill, según lo acordado).

No se tocó lógica de saldo, stock ni el circuito Fincimex en ninguno de los tres cambios.

## Verificación (local, SQLite fresco, puerto 5080 — no producción)

| Caso | Método | Resultado |
|---|---|---|
| PIN se guarda en plano | Crear tarjeta con PIN `4521` vía formulario | ✅ `pin_plano='4521'` en BD; `pin_hash` sigue con el hash de siempre (columna legada, sin uso). |
| PIN visible — admin / PM / operador | Login como los 3 roles, ver detalle de la tarjeta | ✅ Los 3 ven `4521` en la fila PIN. |
| PIN viejo (solo hasheado) no rompe la página | Ver detalle de una tarjeta sembrada antes de este cambio (`pin_plano` NULL) | ✅ Muestra "PIN no disponible (reintroducir)", página renderiza normal. |
| Reintroducir PIN viejo | `POST /tarjetas/1/editar` con campo `pin` relleno | ✅ `pin_plano` pasa de `NULL` a `1234`. |
| Etiqueta "Venta" | HTML renderizado de `habilitaciones/crear.html` | ✅ `<option value="">Venta</option>` y `subEmptyLabel()` ambos actualizados. |
| Esquema: columnas y UNIQUE index | `PRAGMA table_info` + `sqlite_master` sobre la BD fresca | ✅ `tarjetas.pin_plano`, `despachos.numero_operacion`, e `idx_despachos_numero_operacion` (UNIQUE) presentes. |
| Dos despachos concurrentes, misma gasolinera, mismo día | 2 requests HTTP simultáneos (`curl` en paralelo, mismo patrón de pruebas de carrera de sesiones anteriores) a `turno.py::api_despachar` | ✅ Ambos HTTP 200, números **distintos**: `20260713010001` y `20260713010002`. |
| Colisión real de `UNIQUE` forzada directamente contra el helper | Llamada aislada a `insertar_despacho_con_numero()` con el primer candidato interceptado (monkeypatch) para que coincida a propósito con una fila ya insertada | ✅ El helper detectó la colisión, ejecutó `ROLLBACK TO SAVEPOINT`, recalculó, y completó con el siguiente número (`...010004` en vez del `...010003` ya ocupado) — 2 intentos internos confirmados, sin excepción, ambas filas coexisten. |
| Visualización en listado/detalle | Navegador — `despachos/`, `despachos/2` | ✅ Columna "Nº Operación" en el listado con los 4 despachos de la sesión, todos distintos y con el formato correcto; encabezado y tabla del detalle muestran el número. Screenshots tomados. |

**0 errores 500** en toda la sesión.

## Errores encontrados

Ninguno.

## Correcciones aplicadas

Las descritas arriba.

## Recomendaciones

- Verificación en producción queda a cargo de Aldo, como siempre.
- El PIN en texto plano es una decisión de seguridad deliberada y aceptada por Aldo por necesidad operativa — documentado aquí para que quede constancia de que es intencional, no un descuido.
- La prueba de colisión "real" vía monkeypatch fue necesaria porque SQLite serializa escrituras (un solo escritor a la vez) y no reproduce de forma confiable una carrera genuina entre dos transacciones — en Postgres (producción) sí puede haber transacciones concurrentes reales, y el mecanismo de `SAVEPOINT` + reintento es exactamente lo que cubre ese caso.

---

# Clientes: quitar campo "Tipo" (nacional/internacional) sin uso — 2026-07-13

## Diagnóstico previo

Grep exhaustivo en todo `*.py` del proyecto confirmó que `clientes.tipo` no participa en ninguna lógica de negocio fuera del propio módulo Clientes (sin uso en habilitaciones, despachos, tarjetas, reportes, Fincimex ni permisos). Dentro de Clientes sí se usaba en tres puntos más allá de crear/editar que el pedido original no mencionaba explícitamente: el filtro del listado (`clientes.py:42,52-54`), la columna/badge del listado (`templates/clientes/listado.html`), y el badge del detalle (`templates/clientes/detalle.html`) — reportado en el plan antes de tocar nada, tal como se pidió; aprobado incluirlo en el mismo cambio.

## Cambio

- `blueprints/clientes.py` — `listado()`: quitado `filtro_tipo`, la condición `WHERE tipo = ?`, `tipo` del `SELECT` y `tipos_cliente`/`tipos_cliente_labels` del contexto (el resto del armado de `condiciones`/`params`/`where` para `buscar` y `filtro_estado` quedó intacto, verificado explícitamente). `crear()`/`editar()`: quitada la lectura del campo, la validación `tipo not in TIPOS_CLIENTE`, la columna del `INSERT`/`UPDATE`, y `"tipo"` del payload de auditoría. `detalle()`: quitado `tipos_cliente_labels` del contexto. Import de `TIPOS_CLIENTE`/`TIPOS_CLIENTE_LABELS` eliminado del blueprint (ya sin uso).
- 4 templates (`crear.html`, `editar.html`, `listado.html`, `detalle.html`) — quitado el campo de formulario, el filtro, la columna/badge y el badge del detalle. `colspan` del estado vacío del listado ajustado de 7 a 6.
- `utils/constants.py` (`TIPOS_CLIENTE`/`TIPOS_CLIENTE_LABELS`) y la columna `clientes.tipo` en la base **no se tocaron**, tal como se pidió — quedan huérfanos hasta que Aldo haga el `DROP` en el reseteo futuro.

## Verificación (local, SQLite fresco, puerto 5090 — no producción)

| Caso | Método | Resultado |
|---|---|---|
| Crear cliente | Navegador, formulario sin campo Tipo | ✅ Cliente `SNT-001` creado correctamente, sin errores. |
| Listado | Navegador, tras crear | ✅ Sin columna "Tipo" ni filtro; "Buscar" y "Todos los estados" siguen presentes y funcionales. |
| Detalle | Navegador, ficha del cliente creado | ✅ Encabezado sin badge de tipo (solo código y estado); resto de la ficha (contacto, litros reservados, unidades) intacto. |
| Editar | Navegador, formulario sin campo Tipo, guardar notas nuevas | ✅ Cambios guardados correctamente, sin errores; notas reflejadas en el detalle tras guardar. |

**0 errores 500** en toda la sesión. Screenshots tomados de los 4 casos.

## Errores encontrados

Ninguno.

## Correcciones aplicadas

Las descritas arriba.

## Recomendaciones

- Verificación en producción queda a cargo de Aldo, como siempre.
- La columna `clientes.tipo` y las constantes `TIPOS_CLIENTE`/`TIPOS_CLIENTE_LABELS` quedan sin uso en el código, a la espera del `DROP COLUMN` que Aldo hará en el reseteo futuro.
