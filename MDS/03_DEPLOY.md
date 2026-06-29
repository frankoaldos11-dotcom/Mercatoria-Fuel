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

Si hay cambios en el schema de base de datos (nuevas tablas o columnas), ejecutar las migraciones manualmente una vez apuntando a la DATABASE_URL de producción:

```powershell
# PowerShell (Windows local, con venv activo)
$env:DATABASE_URL="postgresql://<usuario>:<password>@<host>/<db>?sslmode=require"
$env:SECRET_KEY="cualquier-valor"
$env:SKIP_MIGRATIONS="false"
python -c "from extensions import bcrypt; from flask import Flask; app = Flask(__name__); bcrypt.init_app(app); from migraciones_pg import ejecutar_migraciones_pg; ejecutar_migraciones_pg(bcrypt)"
```

Después de ejecutar las migraciones, volver a establecer `SKIP_MIGRATIONS=true` en las variables de entorno de Render para que no se ejecuten en cada deploy.

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

## CREAR NUEVA BASE DE DATOS POSTGRESQL EN RENDER

Necesario cuando expire el free tier (2026-07-26) o al migrar de entorno:

### Paso 1 — Crear la BD en Render
1. Entrar a [render.com](https://render.com) → **New → PostgreSQL**
2. Nombre: `mercatoria-fuel-db` | Plan: Free (o Starter $7/mes tras expiración)
3. Region: `Oregon (US West)` (misma que el web service)
4. Copiar la **Internal Database URL** (formato `postgresql://user:pass@host/db`)

### Paso 2 — Conectar al web service
1. En el web service `mercatoria-fuel` → **Environment**
2. Actualizar (o añadir) la variable `DATABASE_URL` con la Internal Database URL copiada
3. Asegurarse de que `SKIP_MIGRATIONS` está en `false` temporalmente

### Paso 3 — Ejecutar migraciones una vez
```powershell
# Desde local con venv activo, apuntando a la nueva DB
$env:DATABASE_URL="postgresql://..."   # Internal URL de Render
$env:SECRET_KEY="cualquier-valor"
$env:SKIP_MIGRATIONS="false"
python -c "from extensions import bcrypt; from flask import Flask; app = Flask(__name__); bcrypt.init_app(app); from migraciones_pg import ejecutar_migraciones_pg; ejecutar_migraciones_pg(bcrypt)"
```

La migración es **idempotente** (`CREATE TABLE IF NOT EXISTS`, `INSERT ... ON CONFLICT DO NOTHING`) — se puede ejecutar más de una vez sin riesgo.

### Paso 4 — Restaurar configuración
1. En Render, volver a establecer `SKIP_MIGRATIONS=true`
2. Hacer trigger de un nuevo deploy (o push cualquier cambio)
3. Verificar en logs de Render que arranca sin errores

### Paso 5 — Verificar con Playwright
- Login admin ✓, dashboard carga ✓, tarjetas seed visibles ✓, portal cliente ✓

---

## INFRAESTRUCTURA PENDIENTE

- **⚠️ PostgreSQL free tier de Render expira 2026-07-26.** Migrar a PostgreSQL Starter (~$7/mes en Render), Supabase Free, o Neon Free antes de esa fecha. Ver pasos arriba.
- Dominio propio pendiente de compra. Apuntarlo a Render cuando esté disponible (SSL automático incluido).
