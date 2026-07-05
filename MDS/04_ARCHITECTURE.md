# 04 — ARCHITECTURE
# Arquitectura del ecosistema Mercatoria
# Versión: 1.0 | Estado: APROBADO

---

## ECOSISTEMA

El ecosistema Mercatoria está compuesto por tres plataformas independientes con repositorios y deploys separados, pero con stack, estética y convenciones de código unificados.

| Plataforma | Repositorio | URL | Estado |
|---|---|---|---|
| Mercatoria Truck | frankoaldos11-dotcom/Mercatoria-Trucks | mercatoria-trucks.onrender.com | v1.0 en producción |
| Mercatoria Fuel | frankoaldos11-dotcom/Mercatoria-Fuel | mercatoria-fuel.onrender.com | En desarrollo activo |
| Mercatoria Assets | pendiente | pendiente | Planificado |

### Aislamiento de bases de datos — regla irrenunciable

**Cada plataforma tiene su propia base PostgreSQL separada desde el día uno. Nunca compartir base entre proyectos.**

`CREATE TABLE IF NOT EXISTS` no protege contra bases compartidas: si dos aplicaciones tienen tablas con el mismo nombre pero esquemas distintos, la que arranca primero fija la estructura de la tabla y la otra queda leyendo columnas que no existen — error 500 "column does not exist" silencioso y difícil de diagnosticar.

**Incidente real (2026-06):** Mercatoria Truck y Mercatoria Fuel compartían `mercatoria-db`. Fuel ejecutó primero sus migraciones y fijó la tabla `usuarios` con su propio esquema. Truck cayó con error 500 en todas las rutas autenticadas. Solución: crear una base separada `mercatoria-fuel-db` para Fuel y ejecutar sus migraciones desde cero.

---

## STACK COMÚN

- **Backend:** Python / Flask con blueprints por módulo
- **Base de datos:** PostgreSQL (producción) / SQLite (desarrollo)
- **Queries:** SQL directo. Sin ORM. Placeholders `%s`/`?` según motor.
- **Frontend:** Jinja2 + Bootstrap 5 + JS vanilla
- **Hosting:** Render.com (App Service + PostgreSQL)
- **Repositorios:** GitHub
- **Deploy:** Automático al push a `master`

---

## ESTRUCTURA DE CARPETAS (estándar)

```
/
├── app.py                  # Inicialización Flask, registro de blueprints
├── database.py             # Único punto de acceso a BD. Wrapper con traducción ?→%s
├── migraciones.py          # Creación de tablas. Idempotente. Sin lógica de negocio.
├── requirements.txt
├── .env.example            # Variables de entorno documentadas (sin valores reales)
├── MDS/                    # Mercatoria Development Standard (este repositorio de docs)
├── blueprints/             # Un archivo por módulo
│   ├── auth.py
│   ├── dashboard.py
│   ├── gasolineras.py
│   └── ...
├── templates/              # Un subdirectorio por módulo
│   ├── base.html
│   ├── dashboard/
│   ├── gasolineras/
│   └── ...
├── static/
│   ├── css/
│   ├── js/
│   └── img/
└── utils/
    ├── auth.py             # Decoradores de autenticación y control de roles
    └── helpers.py          # Funciones auxiliares compartidas
```

---

## PRINCIPIOS DE ARQUITECTURA

**Inventarios por movimientos:** El stock de cualquier depósito o gasolinera se calcula siempre como la suma de todos los movimientos asociados. Nunca hay un campo `stock_actual` que se modifique directamente.

**Tabla movimientos como log central:** Todo cambio de inventario genera un registro en `movimientos`. Es la fuente de verdad del sistema. Solo inserción, nunca modificación.

**Operaciones atómicas:** Cualquier operación que modifique más de una tabla (ej: reasignación de reservas, confirmación de transferencia) debe ser atómica. Si falla cualquier parte, no se guarda nada.

**Sin borrado físico:** Los registros nunca se eliminan. Se desactivan cambiando el campo `estado` o `activo`. Las anulaciones cambian estado y generan auditoría.

**Módulos aislados:** TL38 tiene sus propias tablas (`movimientos_tl38`) completamente separadas del inventario de Mercatoria. No hay joins entre ambas operaciones.

---

## MODELO DE DATOS CENTRAL (Mercatoria Fuel)

Las tablas están documentadas en detalle en el Plan Técnico v1. Las relaciones principales:

```
gasolineras ──── subinventarios (1:N)
gasolineras ──── tarjetas (1:N)
clientes ──────── vehiculos (1:N)
clientes ──────── choferes (1:N)
clientes ──────── subinventarios (1:N, nullable)
movimientos ──── gasolineras, depositos, tarjetas, clientes, vehiculos, choferes (N:1 nullable)
despachos ──────── tarjetas, vehiculos, choferes, clientes, gasolineras (N:1)
conciliaciones ── gasolineras (N:1)
```

---

## ROLES DEL SISTEMA

Cuatro roles activos en Mercatoria Fuel. Los roles legacy (`pm`, `operario`, `supervisor`) están eliminados del selector de creación de usuarios; el backend los reconoce pero no los acepta como nuevos.

| Rol | Código | Acceso |
|---|---|---|
| Administrador | `admin` | Todo: configuración, usuarios, financiero, operaciones |
| Puesto de Mando | `puesto_de_mando` | Toda la operación sin información financiera. Sin gasolinera asignada. Puede crear y gestionar transferencias completas. |
| Operador Gasolinera | `operador_gasolinera` | Acotado a la gasolinera asignada vía `usuarios.gasolinera_id`. Solo despachos, revisión operativa y escaneo QR. No crea transferencias. |
| Cliente | `cliente` | Solo su portal propio (historial, consumo, unidades). |

**Ocultación financiera:** los bloques de información financiera (saldos en CUP, detalles de recarga, reportes económicos) se guardan tras `{% if session.get('rol') in ('admin',) %}`. El rol `puesto_de_mando` no accede a información financiera.

**Roles legacy** (reconocidos en backend como obsoletos, no seleccionables en UI): `pm`, `supervisor`, `operario`.

---

## FUTURAS INTEGRACIONES PREVISTAS

La arquitectura actual está preparada para:

- **Mercatoria Truck ↔ Fuel:** compartir catálogo de vehículos y choferes
- **App móvil:** la API de Flask puede exponerse con autenticación por token
- **Importación Excel masiva:** ya implementada en Sprint 2, extensible a otros módulos
- **Lectores QR/NFC:** campo `codigo_qr` reservado en tablas de vehículos y tarjetas para Sprint futuro
- **Multi-IA:** el MDS v2.0 contempla orquestación entre modelos
