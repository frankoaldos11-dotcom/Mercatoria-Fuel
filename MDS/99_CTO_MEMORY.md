# 99 — CTO MEMORY
# Memoria técnica del proyecto para el CTO
# Versión: 1.0 | Última actualización: Junio 2026

Este documento resume el contexto técnico que el CTO (ChatGPT) necesita conocer al inicio de cada sesión de revisión. Se actualiza al cierre de cada sprint.

---

## CONTEXTO DEL PROYECTO

Mercatoria Fuel es el sistema de control operacional de combustible de Mercatoria S.R.L. Controla el combustible desde su entrada al país (Mariel/Marina) hasta la conciliación final en las gasolineras propias.

La operación real fue documentada a partir de tres chats de WhatsApp (Guanabacoa, La Shell, Puesto de Mando) y nueve Excel de control mensual. Esa documentación tiene prioridad sobre cualquier supuesto técnico.

---

## DECISIONES QUE NO SE REVIERTEN

- Stock calculado desde movimientos. Nunca campo editable.
- Tarjetas con saldo usable y saldo retenido separados.
- TL38 en tablas aisladas, nunca mezclado con Mercatoria.
- Vehículos y choferes unificados en módulo "Unidades".
- Playwright MCP obligatorio en cierre de cada sprint.

---

## STACK Y CONVENCIONES

- Flask + PostgreSQL/SQLite + Bootstrap + Jinja2
- SQL directo con wrapper database.py (sin ORM)
- Blueprints por módulo
- Migraciones idempotentes en migraciones.py
- SKIP_MIGRATIONS=true en Render
- Todo en `utils/auth.py` para autenticación

---

## ESTADO AL CIERRE DEL SPRINT 8

Ver 05_PROJECT_STATUS.md para estado actualizado.

Sprints cerrados: 1, 2, 3, 4, 5, 6, 7, 8.
Sistema v1.0 completo en producción desde Sprint 6 (portal cliente, TL38, reportes, dashboard ejecutivo).
Sprint 8 cerró con: permisos `puesto_de_mando` en transferencias, visibilidad de combustible sin distribuir, subinventarios consolidados por cliente, tabla despachos realizados en detalle gasolinera, botón Ver en transferencias, reasignación de gasolinera en tarjeta.

---

## INFRAESTRUCTURA CRÍTICA

- PostgreSQL free tier de Render expira 2026-07-26. Acción requerida antes de esa fecha.
- Dominio propio pendiente de compra.

---

## INCIDENTES RESUELTOS (lecciones permanentes)

**Bases de datos compartidas (2026-06):** Truck y Fuel compartían `mercatoria-db`. Fuel fijó la tabla `usuarios` primero; Truck cayó con 500 en todas sus rutas. Resolución: base `mercatoria-fuel-db` separada. Regla permanente: una base por proyecto desde el día uno.

**SQLite efímero (2026-06):** Mercatoria Fuel estuvo meses en producción sin persistencia real. Los datos desaparecían en cada deploy porque `DATABASE_URL` no estaba definida en Render y la app caía a SQLite (archivo local, efímero). No era expiración de free tier. Resolución: añadir `DATABASE_URL` en variables de entorno de Render y ejecutar migraciones PG.

**Refs/heads/master corrupto (2026-07):** El archivo `.git/refs/heads/master` quedó con 40 bytes nulos tras un cierre abrupto de Claude Code. Síntoma: `git status` y `git log` fallaban. Resolución: `git fsck` identificó el último commit bueno (`036feb2`); se escribió el SHA correcto en el ref. Regla permanente: diagnosticar con `git fsck` + `git reflog` antes de reparar; nunca reparar a ciegas.

---

## ROLES DEL ECOSISTEMA

- CEO (Aldo): visión, prioridades, decisión final de negocio
- CTO (ChatGPT): arquitectura, metodología, revisión técnica
- Senior Software Engineer (Claude Code): implementación
- Tech Lead / Arquitecto (Claude Chat): análisis, plan técnico, prompts
- QA (Playwright MCP): validación automática en producción
