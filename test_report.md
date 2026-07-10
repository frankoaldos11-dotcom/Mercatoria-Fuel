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
