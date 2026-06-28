# 06 — CHANGELOG
# Historial de cambios Mercatoria Fuel
# Versión: 1.0

---

## Sprint 1 — Infraestructura base
**Fecha:** Junio 2026

- Repositorio GitHub creado: Mercatoria-Fuel
- Flask + PostgreSQL/SQLite configurado con wrapper database.py
- Sistema de login con roles: admin, pm, operario, supervisor, cliente
- Dashboard con 8 cards estructurales (datos en cero)
- CRUD completo de Gasolineras
- Módulo TL38 en sidebar con badge "Próximamente"
- Deploy en Render: mercatoria-fuel.onrender.com
- Seed: usuario admin@mercatoria.com
- Hardening: rutas centralizadas, decoradores en utils/auth.py, headers de seguridad
- Fix: ruta raíz `/` con redirección correcta según estado de sesión
- Fix: datetime('now') → NOW() para compatibilidad PostgreSQL

---

## Sprint 2 — Clientes, Vehículos, Choferes
**Fecha:** Junio 2026
**Commit:** 2acf1e7

- CRUD completo de Clientes con vista de detalle integrada
- Seed automático: PMA, UNFPA, Caritas Cuba, SEISA, Mercatoria Interna
- Módulo Unidades (Vehículos + Choferes unificados): listado, crear, editar, importar Excel
- Badges de licencia vencida (rojo) y por vencer ≤30 días (amarillo)
- Card "Licencias por vencer" en dashboard con alerta naranja
- Importación masiva desde .xlsx con UPSERT por chapa / CI
- PRAGMA foreign_keys = ON en SQLite
- openpyxl añadido a requirements

---

## Sprint 3 — Depósitos, Recepciones, Transferencias
**Fecha:** Junio 2026

- CRUD completo de Depósitos con stock calculado desde movimientos
- Recepciones con flujo: crear → confirmar → insertar en movimientos
- Transferencias con flujo: salida (baja depósito) → llegada (sube gasolinera)
- Dashboard: inventario total y combustible en tránsito con datos reales
- Validación: no transferir si depósito sin stock suficiente
- Migraciones idempotentes reestructuradas (migraciones_pg.py)

---

## Sprint 4 — Tarjetas y Subinventarios
**Fecha:** Junio 2026
**Estado:** En curso

- Tablas: tarjetas, recargas_tarjetas, devoluciones_tarjetas
- Saldo usable y saldo retenido como campos separados
- Flujo de devolución retenida: registrar → liberar
- Subinventarios por gasolinera con prioridades
- Reasignación de reservas como movimiento auditado
- Dashboard: tarjetas con bajo saldo y devoluciones pendientes con datos reales
- Seed de tarjetas reales de La Shell
