# Reporte de Pruebas — 2026-07-05

## Páginas probadas

| URL | Título | Resultado |
|-----|--------|-----------|
| `/login` | Iniciar Sesión | ✅ |
| `/dashboard` | Dashboard | ✅ |
| `/transferencias/` | Transferencias — listado | ✅ |
| `/gasolineras/` | Gasolineras — listado | ✅ |
| `/gasolineras/1` | La Shell — detalle | ✅ |
| `/gasolineras/2` | Berroa — detalle | ✅ |

## Errores encontrados

| Tipo | Descripción | Estado |
|------|-------------|--------|
| 500 Server Error | `/gasolineras/1` fallaba con TypeError por `fecha_despacho[:16]` en datetime de PostgreSQL | ✅ Corregido en commit `8e8293a` (filtro `\|string` en Jinja2) |
| 0 errores de consola JS | Sin errores en ninguna página verificada | ✅ |

## Screenshots tomados

- `sprint8_i1i2ci5_transferencias_listado.png` — Listado de transferencias con botón "Ver" (I5) y badge "Sin distribuir" (I2c)
- `sprint8_i3i4_gasolinera_detalle.png` — La Shell detalle: subinventarios consolidados (I3), tabla despachos (I4), columna L. distribuidos (I2d)
- `sprint8_i4_gasolinera_berroa_detalle.png` — Berroa detalle: mismas secciones

## Correcciones aplicadas

### ISSUE 1 — puesto_de_mando puede crear/gestionar transferencias
- `_requiere_admin_pm()` en `transferencias.py` ahora usa `_ROLES_TRANSFERENCIAS = ["admin", "pm", "puesto_de_mando"]`
- Botones "Nueva transferencia" y "Gestionar" en `listado.html` actualizados

### ISSUE 2a — Columna `litros_distribuidos` en DB
- `migraciones_pg.py`: `ALTER TABLE transferencias ADD COLUMN IF NOT EXISTS litros_distribuidos NUMERIC(14,2) DEFAULT 0`
- `migraciones.py`: mismo ADD COLUMN para SQLite local (REAL DEFAULT 0)

### ISSUE 2b — `distribuir()` actualiza `litros_distribuidos`
- `blueprints/transferencias.py`: `UPDATE transferencias SET litros_distribuidos = COALESCE(litros_distribuidos, 0) + ?` tras cada distribución

### ISSUE 2c — Badge "Sin distribuir" en listado de transferencias
- `listado()` SELECT incluye `t.litros_distribuidos`
- Template muestra badge ámbar "Sin distribuir: X L" si `litros_recibidos - litros_distribuidos > 0.01`
- Verificado: todas las transferencias recibidas muestran badge (litros_distribuidos = 0 por defecto)

### ISSUE 2d — Columna "L. distribuidos" en detalle gasolinera
- Query de transferencias en `detalle()` incluye `t.litros_distribuidos`
- Template `detalle.html`: columna "L. distribuidos" con sub-badge de pendiente

### ISSUE 3 — Subinventarios consolidados por cliente
- `detalle()` en `gasolineras.py`: agregación Python post-fetch; una fila por `cliente_id` con suma de `litros_reservados`
- `suma_reservados` sigue computándose desde la lista raw (correcto)

### ISSUE 4 — Tabla "Despachos realizados"
- Query en `detalle()`: JOIN despachos→clientes→vehiculos→tarjetas
- Sección nueva en `detalle.html` antes de "Transferencias recibidas"
- **Bug detectado y corregido**: `fecha_despacho[:16]` fallaba en PostgreSQL (datetime object). Fix: `(d.fecha_despacho|string)[:16]`

### ISSUE 5 — Botón "Ver" en transferencias recibidas/anuladas
- Template: para `estado != 'en_transito'`, muestra `<a href="/transferencias/{{ t.id }}/gestionar" class="btn btn-secondary btn-sm">Ver</a>`

### Archivos de debug eliminados
- `conciliacion_crear_html.txt` y `conciliacion_crear_html2.txt` eliminados del repo

## Commits del sprint

| Hash | Mensaje |
|------|---------|
| `e8089ef` | PM permiso transferencias + visibilidad combustible sin distribuir + consolidar subinventarios por cliente + tabla despachos realizados + boton ver transferencias |
| `8e8293a` | fix: usar filtro \|string en fecha_despacho para compatibilidad SQLite/PostgreSQL |
| `036feb2` | respaldo antes de produccion (debug txt files) |

## Recomendaciones

- **I2b trazabilidad futura**: actualmente `litros_distribuidos` acumula cada vez que se llama `distribuir()`. Si se necesita resetear (transferencia devuelta parcialmente), será necesario un mecanismo de ajuste.
- **I3 edición de subinventarios consolidados**: los botones "Editar/Toggle/Mover" en filas consolidadas apuntan al primer subinventario del cliente. Considerar una vista de subinventarios individuales por cliente si se necesita gestión granular.
- **Test de I1 con rol puesto_de_mando**: verificar manualmente en producción con un usuario de ese rol.
- **Backfill de litros_distribuidos**: las transferencias históricas tienen `litros_distribuidos = 0` aunque ya fueron distribuidas. Si es necesario, aplicar un UPDATE basado en movimientos de tipo `asignacion_tarjeta`.
