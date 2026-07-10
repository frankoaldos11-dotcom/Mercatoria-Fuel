# Reporte de Pruebas — 2026-07-10

## Commit verificado
`df9ec65` — Nuevo modelo saldo Fincimex: bolsón USD generado en recepción, factor configurable, asignación a tarjetas, bloqueo duro en despacho, aviso saldo vs físico por gasolinera

## Páginas probadas

| # | URL | Resultado | Notas |
|---|-----|-----------|-------|
| 1 | /login | ✅ | Login admin OK, redirige a /dashboard |
| 2 | /tarjetas | ✅ | Bolsón panel ($0.00), columnas SALDO (USD) / LITROS equiv., botón "Saldo USD" en acciones |
| 3 | /tarjetas/1 | ✅ | KPI "Saldo Fincimex (USD): $0.00 / ≈ 0.00 L equiv. / Factor: 0.9 $/L" |
| 4 | /tarjetas/1/asignar-saldo | ✅ | Página nueva carga, bolsón $0.00 visible, calculador litros-equiv en JS |
| 5 | /gasolineras | ✅ | Columnas "Saldo Fincimex (USD)" y "LITROS equiv." en tabla |
| 6 | /gasolineras/1 | ✅ | Panel "Tarjetas Fincimex activas" con 5 tarjetas, total $0.00, botones "Asignar" por tarjeta |
| 7 | /transferencias/crear | ✅ | Aviso JS sin bloqueo al seleccionar La Shell + Gasolina Especial. Botón permanece activo |
| 8 | /configuracion | ✅ | Parámetro "Factor de conversión litro→USD" visible con valor 0.90 y hint descriptivo |

## Errores encontrados

Ninguno. Todas las páginas cargaron sin errores HTTP ni de consola.

## Screenshots tomados

- `fincimex_01_tarjetas_listado.png` — /tarjetas con bolsón panel y columnas USD
- `fincimex_02_tarjeta_detalle.png` — /tarjetas/1 con KPI Saldo Fincimex USD
- `fincimex_03_asignar_saldo.png` — /tarjetas/1/asignar-saldo (nueva página)
- `fincimex_04_gasolineras_listado.png` — /gasolineras con columnas Fincimex
- `fincimex_05_gasolinera_detalle.png` — /gasolineras/1 con panel tarjetas Fincimex
- `fincimex_06_transferencia_aviso.png` — /transferencias/crear con aviso JS (sin bloqueo)
- `fincimex_07_configuracion.png` — /configuracion con factor_litro_usd = 0.90

## Correcciones aplicadas

Ninguna post-commit.

## Comportamiento verificado

| Feature | Estado |
|---------|--------|
| Bolsón general Fincimex en /tarjetas | ✅ $0.00 (sin recepciones aún) |
| Columnas SALDO (USD) / LITROS equiv. en listado tarjetas | ✅ |
| KPI Saldo Fincimex (USD) en detalle tarjeta | ✅ |
| Página /tarjetas/id/asignar-saldo (nueva) | ✅ |
| Panel tarjetas Fincimex en /gasolineras/id | ✅ 5 tarjetas activas en La Shell |
| Botones "Asignar" en panel gasolinera | ✅ |
| Columnas Fincimex en listado gasolineras | ✅ |
| factor_litro_usd en /configuracion | ✅ valor 0.90 |
| Aviso JS en transferencias/crear (no bloqueo) | ✅ botón sigue activo |
| Bloqueo duro en despacho por saldo_usd insuficiente | ⚠️ No probado end-to-end |

## Recomendaciones

1. **Acción urgente antes del próximo despacho**: Todas las tarjetas tienen saldo_usd = $0.00. Ningún despacho con tarjeta Fincimex pasará hasta que un admin asigne saldo USD desde /tarjetas/id/asignar-saldo o se confirme una recepción en depósito (que genera el bolsón automáticamente).

2. **Ciclo completo pendiente de prueba manual**: recepción → bolsón → asignar saldo → habilitación → intentar despachar sin saldo → verificar bloqueo.

3. **Aviso cobertura en gasolineras**: El aviso de litros equiv > stock físico aparecerá cuando haya saldo USD asignado a tarjetas.

4. **factor_litro_usd no retroactivo**: Por diseño, aplica solo a nuevas recepciones.
