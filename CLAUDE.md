# CLAUDE.md — Mercatoria Fuel

## PLAN MODE — REGLA PERMANENTE

Antes de implementar cualquier cambio en este proyecto, siempre:

1. Inspecciona los archivos afectados
2. Presenta un plan en formato de tabla con: qué se cambia, complejidad (baja/media/alta) y archivos afectados
3. Espera aprobación explícita de Aldo antes de escribir una sola línea de código
4. Solo después de recibir "aprobado" o "dale" procedes con la implementación

Esta regla aplica a todos los prompts, sin excepción. Si el prompt dice "implementa X", igual presentas el plan primero.

La única excepción es cuando el prompt dice explícitamente "sin plan, implementa directo".

## POST-COMMIT PLAYWRIGHT — REGLA PERMANENTE

Después de cada commit en este proyecto, siempre:

1. Usa Playwright (mcp__playwright__*) para verificar las páginas afectadas por el cambio en producción (https://mercatoria-fuel.onrender.com)
2. Toma screenshots de cada página verificada
3. Lee la consola del navegador para detectar errores JS o HTTP
4. Genera (o actualiza) `test_report.md` en la raíz del proyecto con:
   - Tabla de resultados ✅ / ❌ / ⚠️ por cada página verificada
   - Lista de screenshots tomados
   - Errores encontrados (consola, HTTP, servidor)
   - Correcciones aplicadas (si las hubo)
   - Recomendaciones pendientes

Esta regla aplica sin excepción después de cualquier `git commit`, sin importar el tamaño del cambio. Si Render está en cold start, espera hasta que la app responda antes de verificar.
