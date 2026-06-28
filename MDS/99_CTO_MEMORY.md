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

## ESTADO AL CIERRE DEL SPRINT 4

Sprint 4 en curso al momento de crear este documento. Ver 05_PROJECT_STATUS.md para estado actualizado.

Sprints cerrados: 1, 2, 3.
Sprint en curso: 4 (Tarjetas y Subinventarios).
Pendientes: 5 (Habilitaciones, Despachos, Conciliación) y 6 (Portal Cliente, TL38, Reportes).

---

## INFRAESTRUCTURA CRÍTICA

- PostgreSQL free tier de Render expira 2026-07-26. Acción requerida antes de esa fecha.
- Dominio propio pendiente de compra.

---

## ROLES DEL ECOSISTEMA

- CEO (Aldo): visión, prioridades, decisión final de negocio
- CTO (ChatGPT): arquitectura, metodología, revisión técnica
- Senior Software Engineer (Claude Code): implementación
- Tech Lead / Arquitecto (Claude Chat): análisis, plan técnico, prompts
- QA (Playwright MCP): validación automática en producción
