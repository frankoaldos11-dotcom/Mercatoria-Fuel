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

---

## SEGURIDAD

- `SECRET_KEY` siempre desde variable de entorno. Nunca hardcodeada.
- Contraseñas hasheadas con `werkzeug.security`. Nunca en claro.
- PINs de tarjetas hasheados al guardar. Nunca mostrar el PIN en claro después del registro.
- CSRF habilitado en todos los formularios que modifican datos.
- Todas las rutas protegidas usan el decorador centralizado de `utils/auth.py`. Sin comprobaciones manuales de sesión en los blueprints.
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

---

## PROMPTS Y SESIONES

- Los prompts describen QUÉ construir y POR QUÉ. Nunca CÓMO encontrar el código.
- Claude Code inspecciona el proyecto antes de modificar cualquier archivo.
- Los cambios relacionados se implementan en una sola pasada.
- Cada prompt termina con el bloque git en una única línea copiable:
  `git add -A ; git commit -m "mensaje" ; git push`
- Al alcanzar ~90% del contexto: finalizar lo que está en progreso, verificar que el sistema corre, commit, ZIP, Resumen de Continuidad, nueva sesión.

---

## MOVIMIENTOS

- Todo cambio de inventario genera un registro en la tabla `movimientos`. Sin excepción.
- Los tipos válidos son: `recepcion`, `transferencia_salida`, `transferencia_entrada`, `recarga_tarjeta`, `despacho`, `ajuste`, `reasignacion`, `habilitacion`.
- La tabla `movimientos` es de solo inserción. Nunca se modifica ni elimina un registro de movimientos. Las correcciones se hacen con movimientos de signo contrario.

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
