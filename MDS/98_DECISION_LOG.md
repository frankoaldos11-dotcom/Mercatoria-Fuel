# 98 — DECISION LOG
# Registro de decisiones técnicas del proyecto
# Versión: 1.0

Cada decisión que afecte la arquitectura, el modelo de datos o el flujo operativo debe registrarse aquí antes de implementarse. Esto evita revertir decisiones ya tomadas y sirve de memoria técnica del proyecto.

Formato: fecha | decisión | alternativas consideradas | motivo

---

## 2026-06 | Vehículos y choferes unificados en módulo "Unidades"

**Decisión:** Un registro de "Unidad" representa un vehículo con su chofer asignado, en lugar de dos módulos separados.
**Alternativas:** Dos módulos separados (Vehículos / Choferes) como especificado originalmente.
**Motivo:** Claude Code tomó esta decisión siguiendo el precedente de Mercatoria Trucks. Simplifica el flujo del operario del PM que trabaja con la combinación vehículo+chofer como unidad. Aprobado al revisar el resultado.

---

## 2026-06 | Stock calculado desde movimientos, nunca campo editable

**Decisión:** Ninguna tabla tiene un campo `stock_actual` que se modifique directamente. El stock se calcula siempre como SUM de movimientos.
**Alternativas:** Campo `stock_actual` con triggers de actualización.
**Motivo:** Trazabilidad completa. Cualquier discrepancia puede auditarse revisando los movimientos. Los triggers ocultan lógica y complican el mantenimiento.

---

## 2026-06 | Tarjetas con dos saldos separados (usable / retenido)

**Decisión:** La tabla `tarjetas` tiene dos campos: `saldo_usable_l` y `saldo_retenido_l`.
**Alternativas:** Un solo campo `saldo_l` con notas en texto libre.
**Motivo:** Las devoluciones retenidas en Fincimex son un fenómeno frecuente en la operación real (observado en los chats de WhatsApp). El saldo usable ≠ saldo físico. Sin esta separación, la conciliación es imposible.

---

## 2026-06 | TL38 aislado en tablas propias

**Decisión:** Los movimientos de TL38 van a `movimientos_tl38`, completamente separada de `movimientos`.
**Alternativas:** Un campo `operacion` en `movimientos` para distinguir Mercatoria de TL38.
**Motivo:** TL38 es una operación diferente que convive en el mismo cupet físico pero no tiene relación financiera con Mercatoria. Mezclarlos en la misma tabla es la causa de los errores de conciliación actuales.

---

## 2026-06 | Gasolineras creadas por el admin, sin seed predefinido

**Decisión:** La tabla `gasolineras` no tiene datos en el seed. El administrador las crea desde la interfaz.
**Alternativas:** Hardcodear las 4 gasolineras confirmadas en el seed.
**Motivo:** Aldo decidió que prefiere crearlas él mismo desde el usuario admin. Más flexible y no requiere conocer los nombres exactos antes del Sprint 1.

---

## 2026-06 | Subinventarios sin límite fijo por gasolinera

**Decisión:** Cada gasolinera puede tener cualquier cantidad de subinventarios con orden de prioridad configurable.
**Alternativas:** Estructura fija: Reserva Cliente + Reserva General + Disponible.
**Motivo:** El CTO identificó en su revisión v1.1 que la jerarquía real es variable. PMA, UNFPA, Caritas, Mercatoria Interna, Reserva General y Disponible son todos subinventarios del mismo tipo con diferente prioridad.

---

## 2026-07 | Bases de datos separadas por proyecto (incidente Truck+Fuel)

**Decisión:** Cada plataforma Mercatoria (Truck, Fuel, Assets) tiene su propia base PostgreSQL. Nunca compartir base entre proyectos.
**Alternativas:** Una sola base `mercatoria-db` con todas las tablas de todos los proyectos.
**Motivo:** Incidente real en junio 2026: Truck y Fuel compartían `mercatoria-db`. Fuel ejecutó primero sus migraciones y fijó el esquema de la tabla `usuarios`. Truck quedó leyendo columnas que no existían → error 500 en todas sus rutas autenticadas. `CREATE TABLE IF NOT EXISTS` no protege contra este escenario: la primera app que corre fija la forma de la tabla. Solución: `mercatoria-fuel-db` separada para Fuel.

---

## 2026-07 | Reasignación de gasolinera en tarjeta Fincimex permitida con auditoría

**Decisión:** Reasignar una tarjeta a otra gasolinera es una operación permitida. Solo cambia `gasolinera_id`; el saldo (`saldo_usable_l`, `saldo_retenido_l`) queda intacto. Se registra en auditoría. Si la tarjeta tiene saldo, se muestra un aviso pero la operación no se bloquea.
**Alternativas:** Bloquear la reasignación si la tarjeta tiene saldo; o no registrar auditoría.
**Motivo:** Operativamente las tarjetas físicas pueden moverse entre gasolineras. El saldo pertenece a la tarjeta, no a la gasolinera. La auditoría es necesaria para trazabilidad. Aprobar el movimiento con aviso es menos disruptivo que bloquearlo.

---

## 2026-07 | DEUDA TÉCNICA ABIERTA — Saldo usable inicial tecleado a mano

**Decisión (pendiente de revisión):** Al crear una tarjeta Fincimex, el campo `saldo_usable_l` inicial se ingresa a mano por el administrador.
**Problema:** Esto permite introducir saldo sin un flujo real de recarga, rompiendo la trazabilidad. Un tarjeta puede aparecer con 5,000 L sin ningún movimiento que lo justifique.
**Acción pendiente:** Evaluar forzar `saldo_usable_l = 0` al crear, con la primera carga de saldo obligatoriamente vía flujo de recarga.

---

## 2026-06 | Playwright MCP obligatorio en cierre de cada sprint

**Decisión:** Ningún sprint puede cerrarse con commit final sin haber ejecutado la verificación Playwright en producción.
**Alternativas:** QA manual o sin QA hasta el final del proyecto.
**Motivo:** Aldo solicitó incluir Playwright en todos los prompts de ambos proyectos (Trucks y Fuel). Garantiza que el deploy en Render funciona correctamente antes de declarar el sprint cerrado.
