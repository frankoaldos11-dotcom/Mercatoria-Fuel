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
