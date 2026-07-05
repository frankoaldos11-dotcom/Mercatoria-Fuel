# 07 — COMMANDS
# Comandos frecuentes del proyecto Mercatoria Fuel
# Versión: 1.0

---

## DESARROLLO LOCAL (Windows + PowerShell)

```powershell
# Activar entorno virtual
cd "E:\Mercatoria Fuel"
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar migraciones (solo en desarrollo)
python migraciones.py

# Arrancar servidor de desarrollo
python app.py
```

---

## GIT — COMANDOS ESTÁNDAR

```powershell
# Commit de cierre de sprint (una sola línea)
git add -A ; git commit -m "Sprint N: descripción" ; git push

# Ver estado actual
git status

# Ver historial reciente
git log --oneline -10

# Crear rama de feature (si se necesita)
git checkout -b feature/nombre-feature
```

---

## PLAYWRIGHT MCP — VERIFICACIÓN EN PRODUCCIÓN

Playwright se usa desde Claude Code como herramienta MCP. No requiere comandos manuales. Se invoca en el prompt de cierre de sprint con instrucciones específicas de qué verificar.

Si Playwright no está disponible en la sesión, añadirlo con:
```powershell
claude mcp add playwright npx @playwright/mcp@latest
```

---

## MIGRACIONES EN PRODUCCIÓN (cuando hay cambios de schema)

```powershell
# Desde local, apuntando a PostgreSQL de Render
$env:DATABASE_URL="postgresql://usuario:password@host/db"
$env:SKIP_MIGRATIONS="false"
python migraciones.py
# Resultado esperado: "Migraciones completadas" sin errores

# Volver a desactivar en Render después
# Variables de entorno → SKIP_MIGRATIONS → true
```

---

## RENDER — ACCIONES MANUALES

- **Ver logs en tiempo real:** Dashboard Render → Mercatoria-Fuel → Logs
- **Reiniciar servicio:** Dashboard Render → Mercatoria-Fuel → Manual Deploy
- **Variables de entorno:** Dashboard Render → Mercatoria-Fuel → Environment

---

## GIT — RECUPERACIÓN DE REF CORRUPTO

Síntoma: `git status`, `git log` o `git push` fallan con errores de objeto inválido o SHA cero. Causa habitual: cierre abrupto de Claude Code mientras tenía el repo bloqueado.

**Paso 1 — Diagnosticar antes de tocar nada:**
```powershell
git fsck --no-dangling    # lista objetos corruptos o colgantes
git reflog                # historial de refs local, muestra último commit bueno
```

**Paso 2 — Confirmar el último commit bueno y que no hay trabajo sin commitear.**

**Paso 3 — Reparar el ref (solo si el SHA del ref es cero):**
```powershell
# Verificar el contenido del ref
Get-Content ".git\refs\heads\master"

# Si muestra 40 ceros, escribir el SHA correcto (obtenido de git reflog)
"<sha-del-último-commit-bueno>" | Out-File -FilePath ".git\refs\heads\master" -Encoding ascii -NoNewline
```

**Paso 4 — Verificar que el repo quedó sano:**
```powershell
git fsck --no-dangling    # debe devolver output vacío
git log --oneline -5
git status
```

**Paso 5 — Si el index también quedó corrupto** (`bad signature 0x00000000`):
```powershell
Remove-Item ".git\index" -Force
git reset HEAD
```

---

## GENERACIÓN DE ZIP PARA NUEVA SESIÓN

```powershell
# Desde el directorio raíz del proyecto
Compress-Archive -Path ".\*" -DestinationPath "..\Mercatoria_Fuel_SprintN.zip" -Force
```
