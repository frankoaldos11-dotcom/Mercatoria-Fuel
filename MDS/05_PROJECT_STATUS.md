# 05 — PROJECT STATUS
# Estado actual de Mercatoria Fuel
# Versión: 1.0 | Última actualización: Junio 2026

---

## ESTADO GENERAL

**Proyecto:** Mercatoria Fuel
**Fase:** Desarrollo activo — Sprint 4 en curso
**URL producción:** https://mercatoria-fuel.onrender.com
**Repositorio:** frankoaldos11-dotcom/Mercatoria-Fuel

---

## SPRINTS

| Sprint | Nombre | Estado | Commit |
|---|---|---|---|
| 1 | Infraestructura base | ✅ Cerrado | 8416ef5 (aprox) |
| 2 | Clientes, Vehículos, Choferes | ✅ Cerrado | 2acf1e7 |
| 3 | Depósitos, Recepciones, Transferencias | ✅ Cerrado | pendiente confirmar |
| 4 | Tarjetas y Subinventarios | 🔄 En curso | — |
| 5 | Habilitaciones, Despachos, Conciliación | ⏳ Pendiente | — |
| 6 | Portal Cliente, TL38, Reportes | ⏳ Pendiente | — |

---

## LO QUE FUNCIONA EN PRODUCCIÓN HOY

- Login / Logout con roles
- Dashboard con cards (inventario total, reservado, disponible, tarjetas bajo saldo, conciliaciones pendientes, despachos pendientes, transferencias en tránsito, alertas, licencias por vencer)
- CRUD completo de Gasolineras
- CRUD completo de Clientes (con seed: PMA, UNFPA, Caritas, SEISA, Mercatoria Interna)
- Módulo Unidades (Vehículos + Choferes unificados) con importación Excel
- CRUD completo de Depósitos con stock calculado desde movimientos
- Recepciones con flujo de confirmación
- Transferencias con flujo salida → llegada
- Tarjetas Fincimex con saldo usable y retenido (Sprint 4 en curso)
- Subinventarios por gasolinera (Sprint 4 en curso)

---

## PENDIENTE ANTES DE PRODUCCIÓN REAL

- Sprint 5: Habilitaciones y despachos (flujo operativo principal)
- Sprint 5: Conciliación diaria
- Sprint 6: Portal cliente
- Sprint 6: Módulo TL38
- Sprint 6: Exportación Excel/PDF
- Migrar PostgreSQL antes de 2026-07-26 (free tier expira)
- Comprar dominio propio

---

## DECISIONES TOMADAS (resumen)

- Vehículos y choferes unificados en módulo "Unidades" (igual que Trucks)
- TL38 aislado en tablas propias, módulo independiente en sidebar
- Stock calculado siempre desde movimientos, nunca campo editable
- Gasolineras creadas por el admin desde la interfaz, sin seed predefinido
- Subinventarios sin límite fijo: cualquier cantidad por gasolinera
- Mercatoria Interna tratada como subinventario propio, no como cliente externo
- Saldo usable y saldo retenido de tarjetas son campos separados
- Playwright MCP obligatorio en el QA de cierre de cada sprint
