# 01 — CLAUDE RULES
# Reglas técnicas obligatorias para todos los proyectos Mercatoria
# Versión: 1.0 | Estado: APROBADO

Estas reglas nunca se rompen. Si Claude Code detecta un conflicto entre una instrucción de un prompt y una regla de este documento, este documento tiene prioridad. Cualquier excepción debe ser aprobada explícitamente por el CEO antes de implementarse.

---

## STACK

- Backend: Python / Flask
- Base de datos: PostgreSQL en producción (Render), SQLite en desarrollo local
- Queries: SQL directo con placeholders `%s` (PostgreSQL) y `?` (SQLite). Nunca ORM.
- Frontend: Jinja2 + Bootstrap + JS vanilla. Sin frameworks JS adicionales.
- Hosting: Render.com
- Repositorios: GitHub bajo frankoaldos11-dotcom

---

## BASE DE DATOS

- El wrapper `database.py` es el único punto de acceso a la base de datos. Nunca crear `conectar()` local en archivos de rutas o blueprints.
- Los placeholders `?` de SQLite se traducen automáticamente a `%s` de PostgreSQL dentro del wrapper. No usar `%s` directamente en las queries de los blueprints.
- Acceder siempre a los resultados de queries por nombre de columna, nunca por índice numérico.
- En SQLite: activar `PRAGMA foreign_keys = ON` al conectar.
- Los stocks e inventarios NUNCA se guardan como campo editable. Siempre se calculan desde la tabla `movimientos` como suma de entradas menos suma de salidas.
- Las migraciones deben ser idempotentes: pueden ejecutarse múltiples veces sin error ni duplicación.
- Variable de entorno `SKIP_MIGRATIONS=true` en Render para evitar la ejecución automática en cada deploy.
- Tipos de columna: usar `NUMERIC` (no `REAL`) para litros, saldos y cualquier valor monetario o de combustible. `REAL` es solo SQLite; `NUMERIC` funciona en ambos motores.
- Toda columna nueva va en `migraciones_pg.py` (producción) **y** en `migraciones.py` (SQLite local). No actualizar solo uno.
- Bloques `DROP` destructivos: nunca incondicionales. Guardarlos tras una variable de entorno (`RESET_SCHEMA=true`) que por defecto no esté activa. Ejecutar una vez, luego retirar el bloque del código y la variable de Render.

### Checklist de compatibilidad SQLite → PostgreSQL

Estos bugs son latentes: no revientan en desarrollo local (SQLite), solo con datos reales en producción (PostgreSQL):

**(a) Slicing de fechas:** `campo[:10]` falla en PG porque `psycopg2` devuelve columnas `DATE`/`TIMESTAMP` como objetos Python `datetime`, no strings. Fix en Jinja2: `(campo | string)[:10]` o `(campo | string)[:16]`.

**(b) Aritmética float/Decimal:** `psycopg2` devuelve columnas `NUMERIC` como `Decimal`, no `float`. Mezclar `Decimal` con `float` o `int` lanza `TypeError`. Fix en templates: `(campo | float)`. Fix en Python: `float(row["campo"])`.

**(c) Funciones SQLite-only:** `strftime('%Y-%m', fecha)` no existe en PostgreSQL. Fix: `SUBSTR(CAST(fecha AS TEXT), 1, 7)`, que funciona en ambos motores.

**(d) Guards de rol:** al migrar a PG con usuarios reales, cualquier ruta que solo tenga `requiere_login` (sin verificar `rol`) queda expuesta. Revisar todas las rutas del panel operativo antes de abrir a usuarios reales.

---

## SEGURIDAD

- `SECRET_KEY` siempre desde variable de entorno. Nunca hardcodeada.
- Contraseñas hasheadas con `werkzeug.security`. Nunca en claro.
- PINs de tarjetas hasheados al guardar. Nunca mostrar el PIN en claro después del registro.
- CSRF habilitado en todos los formularios que modifican datos.
- Todas las rutas protegidas usan el decorador centralizado de `utils/auth.py`. Sin comprobaciones manuales de sesión en los blueprints.
- **Guard de ROL, no solo de login:** toda ruta del panel operativo debe verificar `session["rol"]` además de autenticación. Solo `requiere_login` no es suficiente — un cliente autenticado puede acceder a tarjetas Fincimex y listados humanitarios. Incidente real: 8 rutas expuestas descubiertas al activar usuarios reales.
- **`session.clear()` al inicio del POST de login, antes de verificar credenciales.** Si solo se limpia en el caso exitoso, un intento fallido deja viva la sesión anterior. Síntoma: roles que se cruzan entre usuarios en la misma máquina.
- **`Cache-Control: no-cache, no-store, must-revalidate`** en `after_request` para todas las páginas autenticadas. Es el segundo vector del cruce de roles (independiente de `session.clear()`): el navegador sirve una página cacheada del usuario anterior. Probar siempre el cruce en ventana de incógnito para no confundir caché viejo con bug de sesión.
- Headers de seguridad en todas las respuestas: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`.
- Logging de errores con `logger.error()`. Nunca `print()` para debug en producción.

---

## CÓDIGO

- Toda la lógica de autenticación y control de roles vive en `utils/auth.py`. Sin duplicación.
- El filtro Jinja2 `fmt_fecha` es el único lugar donde se formatean fechas en templates. Nunca formatear fechas en línea.
- Usar dot notation en Jinja2: `viaje.id`, nunca `viaje["id"]`.
- Usar `NULLIF` para campos de precio o cantidad que puedan llegar vacíos desde el formulario.
- Los campos numéricos de formularios se validan antes de insertar: no negativos, no vacíos cuando son obligatorios.
- Sin código muerto: si se elimina una funcionalidad, se eliminan también sus imports, rutas y templates.
- Sin `conectar()` local en ningún archivo que no sea `database.py`.
- **JS en scope global:** las funciones JS llamadas desde `onchange`, `onclick` o `oninput` en el HTML deben estar definidas en scope global, nunca dentro de un IIFE (`(function(){...})()`) ni de un listener `DOMContentLoaded`. Si están encapsuladas, el atributo inline no las encuentra y falla en silencio.

---

## PROMPTS Y SESIONES

- Los prompts describen QUÉ construir y POR QUÉ. Nunca CÓMO encontrar el código.
- Claude Code inspecciona el proyecto antes de modificar cualquier archivo.
- Los cambios relacionados se implementan en una sola pasada.
- Cada prompt termina con el bloque git en una única línea copiable:
  `git add -A ; git commit -m "mensaje" ; git push`
- Al alcanzar ~90% del contexto: finalizar lo que está en progreso, verificar que el sistema corre, commit, ZIP, Resumen de Continuidad, nueva sesión.
- **Frontera de producción:** ni Claude Code ni Playwright reciben credenciales de la base de datos de producción. Las acciones directas contra la base de prod (ejecutar migraciones, seeds, correcciones de datos) las ejecuta una persona desde su terminal local, apuntando a la `DATABASE_URL` de Render.

---

## MOVIMIENTOS

- Todo cambio de inventario genera un registro en la tabla `movimientos`. Sin excepción.
- Los tipos válidos son: `recepcion`, `transferencia_salida`, `transferencia_entrada`, `recarga_tarjeta`, `despacho`, `ajuste`, `reasignacion`, `habilitacion`.
- La tabla `movimientos` es de solo inserción. Nunca se modifica ni elimina un registro de movimientos. Las correcciones se hacen con movimientos de signo contrario.
- El stock que muestra el **listado** debe coincidir al litro con el que muestra el **detalle**. Reutilizar la misma consulta SQL de acumulación en ambas vistas; nunca duplicar la lógica de cálculo.

---

## REGLAS DE NEGOCIO FUEL

- No transferir combustible a una gasolinera sin al menos una tarjeta Fincimex activa del mismo tipo de combustible. Aviso en frontend + bloqueo duro en backend en `confirmar_llegada`. Esta validación es irrenunciable.
- Distribución de litros: la suma asignada a tarjetas debe igualar exactamente los litros de la llegada. Validar en frontend (suma en tiempo real) y en backend antes de confirmar.
- La distribución a tarjetas puede quedar pendiente pero nunca invisible: mostrar siempre cuánto se recibió, cuánto se distribuyó y cuánto queda sin distribuir (columna `litros_distribuidos`, badge "Sin distribuir: X L").
- Subinventarios del mismo cliente se consolidan en una sola fila con la suma de `litros_reservados`. No mostrar una fila por cada subinventario individual.
- Reasignar una tarjeta Fincimex a otra gasolinera: solo cambia `gasolinera_id`. El saldo (`saldo_usable_l`, `saldo_retenido_l`) queda intacto. Registrar en auditoría. Mostrar aviso si tiene saldo, pero permitir la operación.

---

## AUDITORÍA

- Toda modificación de datos registra en `auditoria`: usuario, acción, tabla, registro_id, valor anterior, valor nuevo, IP, user_agent, fecha.
- Las anulaciones no borran registros: cambian el campo `estado` a `anulada` y generan registro de auditoría.

---

## QA

- Antes de cada commit de cierre de sprint, verificar con Playwright MCP en la URL de producción.
- El flujo mínimo a verificar por sprint está definido en `02_QA_MASTER.md`.
- Si Playwright detecta errores, se corrigen antes del commit. Nunca hacer commit con errores conocidos.

---

## ESTÉTICA

- Todos los módulos siguen la misma estética: mismo sidebar, mismo navbar, mismos componentes Bootstrap, mismos badges.
- No inventar estilos nuevos en cada módulo. Reusar los existentes.
- El saldo retenido de tarjetas siempre se muestra en naranja/amarillo, nunca en el mismo color que el saldo usable.
- Las licencias vencidas o por vencer (≤30 días) siempre se muestran con badge de alerta.
- **Botón de acción como primera columna** en todas las tablas del sistema. El usuario no debe desplazarse hasta el final de la fila para actuar.
