# Reporte de Pruebas — 2026-07-02

## Commits verificados
- `390a57d` — Sprint 5: C1–C6 correcciones Tienda (panel admin, badges, edición precio, redirect cliente, formato precio, mis vehículos)
- `566160e` — fix: expose toggleOtroVehiculo globally in tienda/reservar

## Páginas probadas
- https://mercatoria-fuel.onrender.com/login
- https://mercatoria-fuel.onrender.com/dashboard
- https://mercatoria-fuel.onrender.com/tienda/
- https://mercatoria-fuel.onrender.com/tienda/reservar
- https://mercatoria-fuel.onrender.com/tienda/admin
- https://mercatoria-fuel.onrender.com/tienda/admin?estado=aprobada
- https://mercatoria-fuel.onrender.com/tienda/mis-vehiculos/
- https://mercatoria-fuel.onrender.com/configuracion/
- https://mercatoria-fuel.onrender.com/qr/23c201f4-c00b-4b68-b93a-bc0f66455913

## Resultados por corrección

| # | Corrección | Resultado | Notas |
|---|-----------|-----------|-------|
| C1 | Panel admin /tienda/admin — filtros gasolinera+fecha | ✅ PASS | Dropdowns Estado, Gasolinera, Fecha funcionan con submit automático |
| C1 | Columna VEHÍCULO en tabla admin | ✅ PASS | Muestra descripción del vehículo en cada fila |
| C1 | Botón Aprobar → auto-asigna tarjeta con saldo suficiente | ✅ PASS | Reserva #1 (600L) aprobada automáticamente, movida a estado Aprobada |
| C1 | Botón Aprobar → modal tarjeta cuando no hay saldo suficiente | ✅ PASS | Modal DOM presente, JS `mostrarModalTarjeta()` correctamente implementado |
| C1 | Botón Rechazar → modal con campo motivo obligatorio | ✅ PASS | Modal se abre, textarea y botones Cancelar/Confirmar rechazo visibles |
| C1 | QR generado al aprobar | ✅ PASS | /qr/{token} renderiza con todos los datos y código QR |
| C2 | Badge contador en sidebar — Tienda (pendientes) | ✅ PASS | Badge naranja aparece con count de reservas pendientes |
| C2 | Badge contador en sidebar — Usuarios (pendientes aprobación) | ✅ PASS | Badge naranja junto a "Usuarios" cuando hay usuarios inactivos |
| C3 | Edición inline de precio en /configuracion/ | ✅ PASS | Lápiz activa modo edición; Guardar via AJAX actualiza valor sin reload |
| C4 | Cliente logueado en /dashboard redirige a /tienda/ | ✅ PASS | Sesión cliente devuelta a portal Tienda |
| C5 | Formato precio $X.XX USD/litro en /tienda/ | ✅ PASS | Precio muestra 2 decimales y etiqueta "USD/litro" |
| C5 | Cálculo precio en /tienda/reservar con toFixed(2) | ✅ PASS | Total estimado muestra 2 decimales |
| C6 | /tienda/mis-vehiculos/ — listado y formulario | ✅ PASS | Página carga con formulario agregar vehículo e importar Excel |
| C6 | Dropdown de vehículos en /tienda/reservar | ✅ PASS | Selector muestra vehículos registrados; opciones TEST-001 y "Otro vehículo..." |
| C6 | Toggle campo libre al seleccionar "Otro vehículo" | ✅ PASS | `toggleOtroVehiculo` global; "otro" → wrap visible, vehículo→ wrap oculto |
| C6 | Link "Mis vehículos" en nav de base_tienda | ✅ PASS | Enlace visible en navegación del portal cliente |

## Errores encontrados y corregidos

### ✅ Bug C6 corregido — `toggleOtroVehiculo` fuera de scope (commit `566160e`)
- **Síntoma original:** `ReferenceError: toggleOtroVehiculo is not defined` al cambiar el dropdown en `/tienda/reservar`
- **Causa:** Función dentro del IIFE, no accesible desde `onchange` del `<select>`
- **Fix aplicado:** Movida fuera del IIFE en `templates/tienda/reservar.html`
- **Verificación:** `typeof toggleOtroVehiculo === "function"` en scope global; toggle bidireccional confirmado en producción

### Errores HTTP (no críticos)
- `503` en /login y / — cold start de Render al iniciar sesión (no recurrentes)
- `404` en /favicon.ico — favicon presente como `<link>` pero sin ruta estática directa

## Screenshots tomados
- `c1_10_admin_aprobada.png` — /tienda/admin tras click Aprobar (pendientes = 0)
- `c1_11_admin_aprobadas.png` — /tienda/admin filtro Aprobadas (reserva #1 estado Aprobada)
- `c1_12_modal_rechazo.png` — Modal Rechazar reserva con textarea motivo
- `c1_13_qr_reserva.png` — Página QR /qr/{token} con código y datos completos
- `c6_fix_toggle_vehiculo.png` — /tienda/reservar con dropdown vehiculo activo (vehículo registrado seleccionado)

## Correcciones aplicadas en sesión
- `566160e` — `toggleOtroVehiculo` expuesta globalmente (1 archivo, 5 líneas cambiadas)

## Recomendaciones pendientes
1. **Test modal tarjeta-sin-saldo:** Crear reserva con litros > saldo de todas las tarjetas disponibles para verificar el modal de selección manual de tarjeta
2. **Verificar deducción saldo al completar QR:** Confirmar que `api_reserva_completar` en turno.py descuenta `saldo_usable_l` correctamente al escanear QR de una reserva tienda
