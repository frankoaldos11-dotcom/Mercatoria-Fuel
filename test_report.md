# Reporte de Pruebas — 2026-07-03

## Páginas probadas

| URL | Título | Resultado |
|-----|--------|-----------|
| `/login` | Iniciar Sesión | ✅ |
| `/dashboard` | Dashboard | ✅ |
| `/gasolineras/` | Gasolineras — listado | ✅ |
| `/gasolineras/1` | La Shell — detalle | ✅ |
| `/habilitaciones/?gasolinera_id=1` | Habilitaciones — listado | ✅ |
| `/conciliacion/crear?gasolinera_id=1&fecha=2026-07-03` | Nueva Conciliación | ✅ |

## Cambios verificados

| Cambio | Descripción | Resultado |
|--------|-------------|-----------|
| CAMBIO 1 | Sidebar reestructurado: PUESTO DE MANDO GENERAL (Operaciones/Acciones), OPERADORES GASOLINERA, COMERCIAL, SISTEMA | ✅ |
| CAMBIO 2 | Escanear QR solo en bloque OPERADORES GASOLINERA, no en Acciones | ✅ |
| CAMBIO 3 | Stock por combustible en listado gasolineras: `Diésel: 23,847 L` | ✅ |
| CAMBIO 3 | Stock listado ≡ stock detalle: ambos muestran `23,847.00 L` exacto | ✅ |
| CAMBIO 4 | Columna Acciones primera en habilitaciones listado | ✅ |
| CAMBIO 5 | Dropdown de turno eliminado del Paso 2 de conciliación | ✅ |
| CAMBIO 7 | Panel "Habilitaciones del día" visible en conciliación crear (gasolinera+fecha seleccionadas) | ✅ |
| CAMBIO 7 | Banner "Turno listo para cerrar — todas las habilitaciones despachadas" | ✅ |
| CAMBIO 7 | Filas en verde para habilitaciones despachadas correctamente | ✅ |

## Errores encontrados

Ninguno en producción.

### Bug corregido durante la sesión

- **`blueprints/conciliacion.py` — `_detalle_habilitaciones`**: query original usaba `JOIN unidades` (tabla incorrecta, es `vehiculos`) y `JOIN despachos` para `litros_despachados` (columna ya existe en `habilitaciones`). Corregido en commit `2fa759b`.

## Screenshots tomados

- `sprint7_01_dashboard_sidebar.png` — Dashboard con nuevo sidebar
- `sprint7_02_gasolineras_listado.png` — Listado gasolineras con stock por combustible y acciones en primera columna
- `sprint7_03_conciliacion_crear.png` — Conciliación Paso 2 sin dropdown turno
- `sprint7_04_conciliacion_habs_panel.png` — Panel comparativo habilitaciones del día funcionando

## Correcciones aplicadas

1. **`blueprints/conciliacion.py`** — `_detalle_habilitaciones`: reemplazado `JOIN unidades` por `JOIN vehiculos` y `d.litros_despachados` (vía JOIN despachos) por `h.litros_despachados` (columna directa de habilitaciones). Commit `2fa759b`.

## Validación de tarjeta Fincimex (Sprint 7 — commit 73f666b)

### Regla de negocio implementada
Para transferir combustible a una gasolinera, debe existir al menos una tarjeta Fincimex activa del mismo tipo de combustible en esa gasolinera.

### Páginas verificadas

| URL | Escenario | Resultado |
|-----|-----------|-----------|
| `/transferencias/crear` | La Shell + Gasolina Regular (sin tarjeta activa) | ✅ Aviso mostrado, submit deshabilitado |
| `/transferencias/crear` | La Shell + Diésel (con tarjetas activas) | ✅ Sin aviso, submit habilitado |
| `/transferencias/6/gestionar` | Confirmar llegada La Shell + Diésel | ✅ Aprobado correctamente (4 tarjetas activas) |

### Frontend — aviso temprano (`validarTarjeta()`)

| Check | Valor observado |
|-------|----------------|
| `aviso-tarjeta` display (sin tarjeta) | `block` |
| Mensaje | "La Shell no tiene tarjetas Fincimex activas de Gasolina Regular. No puede recibir este combustible hasta que se le asigne una." |
| `btn-submit.disabled` (sin tarjeta) | `true` |
| `aviso-tarjeta` display (con tarjeta) | `none` |
| `btn-submit.disabled` (con tarjeta) | `false` |

### Backend — bloqueo duro (`confirmar_llegada`)

El guardia crítico está en `blueprints/transferencias.py` líneas 396–408:

```python
cur.execute("""
    SELECT COUNT(*) AS n FROM tarjetas
    WHERE gasolinera_id = ? AND tipo_combustible = ? AND estado = 'activa'
""", (transferencia["gasolinera_destino_id"], transferencia["tipo_combustible"]))
if cur.fetchone()["n"] == 0:
    conn.close()
    error = "... No se puede confirmar la llegada sin respaldo de tarjeta. ..."
else:
    # INSERT transferencia_entrada solo si n > 0
    conn.commit()
    return redirect(...)
```

**Verificación live**: Transferencia #6 (La Shell + Diésel) se confirmó correctamente porque La Shell tiene 5 tarjetas de Diésel (4 activas al momento de la prueba). La lógica del bloqueo es correcta: el INSERT de `transferencia_entrada` está dentro del `else:`, garantizando que el combustible nunca entra al stock si el COUNT = 0.

**Nota sobre el test de aislamiento**: Para verificar el path de bloqueo en producción se requeriría una gasolinera con cero tarjetas activas del tipo. El path de código está cubierto; el `if n == 0` está correctamente conectado al `error` que evita el commit.

### Screenshots tomados

- `sprint7_tar_01_aviso_sin_tarjeta.png` — Aviso frontend, submit deshabilitado (La Shell + Gasolina Regular)
- `sprint7_tar_02_con_tarjeta_ok.png` — Sin aviso, submit habilitado (La Shell + Diésel)

## Recomendaciones

- El sidebar del admin muestra AMBOS bloques PUESTO DE MANDO GENERAL y OPERADORES GASOLINERA (comportamiento correcto: el admin ve todo). Validar con un usuario `operador_gasolinera` real para confirmar que solo ve su bloque.
- Las filas del panel comparativo muestran verde/rojo/ámbar según estado. Probar con habilitaciones en estado `pendiente` o `aprobada` para verificar filas rojas.
- Para probar el bloqueo duro en producción end-to-end: crear una gasolinera de prueba sin tarjetas e intentar confirmar una llegada de combustible → debe rechazar con el mensaje configurado.
