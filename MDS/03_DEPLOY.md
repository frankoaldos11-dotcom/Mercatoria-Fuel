# 03 — DEPLOY
# Procedimiento de despliegue Mercatoria
# Versión: 1.0 | Estado: APROBADO

---

## ENTORNOS

| Entorno | URL | Base de datos | Migraciones |
|---|---|---|---|
| Desarrollo local | http://localhost:5000 | SQLite (mercatoria_fuel.db) | Automáticas al arrancar |
| Producción | https://mercatoria-fuel.onrender.com | PostgreSQL (Render) | SKIP_MIGRATIONS=true |

---

## VARIABLES DE ENTORNO REQUERIDAS

```
DATABASE_URL=postgresql://...    # Proporcionada por Render automáticamente
SECRET_KEY=...                   # Cadena aleatoria segura, mínimo 32 caracteres
SKIP_MIGRATIONS=true             # Siempre true en producción
```

---

## DESPLIEGUE EN RENDER

El despliegue es automático al hacer push a la rama `master`. Render detecta el push, construye la imagen y reinicia el servicio.

Tiempo estimado de cold start: ~30 segundos.

Si hay cambios en el schema de base de datos (nuevas tablas o columnas), ejecutar las migraciones manualmente una vez desde la consola de Render o desde local apuntando a la DATABASE_URL de producción:

```powershell
$env:DATABASE_URL="postgresql://..."
$env:SKIP_MIGRATIONS="false"
python migraciones.py
```

Después volver a establecer SKIP_MIGRATIONS=true en las variables de entorno de Render.

---

## DESPLIEGUE LOCAL (Windows + PowerShell)

```powershell
cd "E:\Mercatoria Fuel"
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migraciones.py
python app.py
```

---

## CIERRE DE SPRINT — CHECKLIST

Antes de dar por cerrado un sprint:

- [ ] Playwright QA pasado sin errores (ver 02_QA_MASTER.md)
- [ ] `git add -A ; git commit -m "Sprint N: descripción" ; git push`
- [ ] Verificar que el deploy en Render se completó sin errores
- [ ] Generar ZIP del proyecto
- [ ] Escribir Resumen de Continuidad
- [ ] Actualizar 05_PROJECT_STATUS.md
- [ ] Añadir entrada en 06_CHANGELOG.md

---

## INFRAESTRUCTURA PENDIENTE

- PostgreSQL free tier de Render expira 2026-07-26. Migrar a PostgreSQL de pago (~$7/mes), Supabase, o Neon antes de esa fecha.
- Dominio propio pendiente de compra. Apuntarlo a Render cuando esté disponible (SSL automático incluido).
