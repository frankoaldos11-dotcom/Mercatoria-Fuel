# Reporte de Pruebas — 2026-06-29

## Páginas probadas
- https://mercatoria-fuel.onrender.com/login
- https://mercatoria-fuel.onrender.com/dashboard (como admin y como operario)
- https://mercatoria-fuel.onrender.com/gasolineras/
- https://mercatoria-fuel.onrender.com/clientes/
- https://mercatoria-fuel.onrender.com/usuarios/
- https://mercatoria-fuel.onrender.com/usuarios/crear
- https://mercatoria-fuel.onrender.com/turno/
- https://mercatoria-fuel.onrender.com/configuracion/
- https://mercatoria-fuel.onrender.com/unidades/crear

## Errores encontrados
- **favicon.ico 404** — Se sirve `favicon.png` en el `<link rel="icon">` pero el navegador también solicita `favicon.ico` automáticamente. Cosmético, no afecta funcionalidad.
- **503 en cold start** — Render free tier tardó ~35 s en despertar. Primera solicitud a `/login` recibió 503 transitorio. Normal en este plan de hosting.
- Sin errores de consola JS en ninguna página de producción.
- Sin errores HTTP 4xx/5xx en rutas de la aplicación.

## Screenshots tomados
- `01_dashboard.png` — Dashboard admin: KPIs completos (Inventario, Operativa, Alertas), badge ADMIN rojo en topbar, sidebar reordenado con 4 secciones
- `02_turno.png` — Página Turno del día: selector gasolinera/fecha/turno + botón "Cargar turno"
- `03_configuracion.png` — Configuración del sistema: "Compra mínima por habilitación" = 500 L, editable
- `04_usuarios_listado.png` — Listado usuarios con badges de rol coloreados (Operario=verde, Cliente=naranja, Admin=rojo)
- `05_dashboard_operario.png` — Dashboard operario: vista simplificada "Habilitaciones pendientes", badge OP verde, botón "Ir al Turno del día"
- `06_unidades_crear_c9.png` — Formulario nueva unidad: link "Añadir cliente nuevo" visible bajo el selector de cliente

## Correcciones aplicadas — Post-launch v1.0 (commit 3dd0514)

| # | Corrección | Resultado |
|---|-----------|-----------|
| C1 | Sidebar URLs con trailing slash — Flask blueprint fix | ✅ PASS |
| C2 | Orden sidebar: OPERACIONES / COMERCIAL / OPERATIVA (con Turno del día) / SISTEMA | ✅ PASS |
| C3 | Campos litros → `type=text inputmode=decimal` (sin flechitas spinner) | ✅ PASS (código aplicado) |
| C4 | CRUD Usuarios completo: crear, listar, badges de rol, redirige con ?ok=1 | ✅ PASS |
| C5 | Página Turno del día (`/turno/`) accesible con selector y layout AJAX | ✅ PASS |
| C6 | Configuración del sistema: compra mínima 500 L, editable por admin | ✅ PASS |
| C7 | Dashboard por rol: admin full / operario simplificado con CTA Turno del día | ✅ PASS |
| C8 | Badge de rol en topbar: nombre de usuario + badge coloreado por rol | ✅ PASS |
| C9 | Botón "Añadir cliente nuevo" en `/unidades/crear` abre `/clientes/crear` en nueva pestaña | ✅ PASS |

## Recomendaciones
- **favicon.ico**: Agregar un `favicon.ico` estático o configurar un redirect para eliminar el 404 cosmético que genera el navegador.
- **Sidebar y roles**: El operario puede ver los links de `/usuarios/` y `/configuracion/` en el sidebar, aunque las rutas están protegidas con `requiere_rol`. Considerar filtrar los ítems del sidebar según `session.get('rol')` para mayor claridad UX.
- **Turno del día — flujo AJAX end-to-end**: La página carga correctamente. El flujo completo (añadir habilitación, aprobar, despachar, cerrar turno) requiere una gasolinera activa y tarjeta con saldo para prueba en producción. No probado en esta sesión por no haber datos suficientes en el entorno.
- **C3 — cuota_mensual_l en /unidades/crear**: Verificar que el campo `cuota_mensual_l` también fue cambiado a `type=text inputmode=decimal` (el commit lo incluye pero no fue probado visualmente con inspección de código fuente de la página).
