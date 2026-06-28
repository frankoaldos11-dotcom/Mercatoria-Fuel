import os
import psycopg2
import psycopg2.extras


def _conectar():
    url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(url)
    return conn


def ejecutar_migraciones_pg(bcrypt):
    if os.environ.get("SKIP_MIGRATIONS") == "true":
        print("[migraciones_pg] SKIP_MIGRATIONS=true — omitiendo migraciones.")
        return

    conn = _conectar()
    cur = conn.cursor()

    print("[migraciones_pg] Ejecutando migraciones (IF NOT EXISTS — idempotente).")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id            SERIAL PRIMARY KEY,
        nombre        TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rol           TEXT NOT NULL DEFAULT 'operario',
        activo        INTEGER NOT NULL DEFAULT 1,
        created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS gasolineras (
        id                 SERIAL PRIMARY KEY,
        nombre             TEXT NOT NULL,
        region             TEXT NOT NULL,
        direccion          TEXT,
        combustible        TEXT NOT NULL,
        capacidad_l        NUMERIC(14,2) NOT NULL DEFAULT 0,
        gestor_responsable TEXT,
        estado             TEXT NOT NULL DEFAULT 'activo',
        created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── columnas añadidas a gasolineras post-v1 ───────────────────────────────
    cur.execute("ALTER TABLE gasolineras ADD COLUMN IF NOT EXISTS provincia TEXT")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subinventarios (
        id                SERIAL PRIMARY KEY,
        gasolinera_id     INTEGER NOT NULL REFERENCES gasolineras(id),
        nombre            TEXT NOT NULL,
        tipo              TEXT NOT NULL DEFAULT 'mercatoria_interna',
        orden_prioridad   INTEGER NOT NULL DEFAULT 0,
        litros_reservados NUMERIC(14,2) NOT NULL DEFAULT 0,
        cliente_id        INTEGER,
        activo            INTEGER NOT NULL DEFAULT 1,
        created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id                       SERIAL PRIMARY KEY,
        tipo                     TEXT NOT NULL,
        fecha                    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        gasolinera_id            INTEGER REFERENCES gasolineras(id),
        deposito_id              INTEGER,
        tarjeta_id               INTEGER,
        cliente_id               INTEGER,
        vehiculo_id              INTEGER,
        chofer_id                INTEGER,
        subinventario_origen_id  INTEGER REFERENCES subinventarios(id),
        subinventario_destino_id INTEGER REFERENCES subinventarios(id),
        litros                   NUMERIC(14,2) NOT NULL DEFAULT 0,
        responsable_id           INTEGER NOT NULL REFERENCES usuarios(id),
        observaciones            TEXT,
        created_at               TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS auditoria (
        id             SERIAL PRIMARY KEY,
        usuario_id     INTEGER REFERENCES usuarios(id),
        accion         TEXT NOT NULL,
        tabla_afectada TEXT,
        registro_id    INTEGER,
        valor_anterior TEXT,
        valor_nuevo    TEXT,
        ip             TEXT,
        user_agent     TEXT,
        fecha          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id                        SERIAL PRIMARY KEY,
        nombre                    TEXT NOT NULL,
        codigo                    TEXT UNIQUE NOT NULL,
        tipo                      TEXT NOT NULL DEFAULT 'internacional',
        contacto_nombre           TEXT,
        contacto_telefono         TEXT,
        contacto_email            TEXT,
        subinventario_reservado_l NUMERIC(14,2) NOT NULL DEFAULT 0,
        notas                     TEXT,
        activo                    INTEGER NOT NULL DEFAULT 1,
        created_at                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehiculos (
        id               SERIAL PRIMARY KEY,
        cliente_id       INTEGER NOT NULL REFERENCES clientes(id),
        chapa            TEXT UNIQUE NOT NULL,
        marca            TEXT,
        modelo           TEXT,
        anio             INTEGER,
        tipo_combustible TEXT NOT NULL,
        cuota_mensual_l  NUMERIC(14,2),
        color            TEXT,
        observaciones    TEXT,
        estado           TEXT NOT NULL DEFAULT 'activo',
        created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS choferes (
        id                   SERIAL PRIMARY KEY,
        cliente_id           INTEGER NOT NULL REFERENCES clientes(id),
        nombre               TEXT NOT NULL,
        ci                   TEXT UNIQUE NOT NULL,
        licencia_numero      TEXT,
        licencia_vencimiento DATE,
        telefono             TEXT,
        observaciones        TEXT,
        estado               TEXT NOT NULL DEFAULT 'activo',
        created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── columnas añadidas a vehiculos post-v2 ─────────────────────────────────
    cur.execute("ALTER TABLE vehiculos ADD COLUMN IF NOT EXISTS chofer_id INTEGER REFERENCES choferes(id)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS depositos (
        id               SERIAL PRIMARY KEY,
        nombre           TEXT NOT NULL,
        region           TEXT NOT NULL,
        direccion        TEXT,
        tipo_combustible TEXT NOT NULL,
        capacidad_l      NUMERIC(14,2) NOT NULL DEFAULT 0,
        responsable      TEXT,
        notas            TEXT,
        estado           TEXT NOT NULL DEFAULT 'activo',
        created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recepciones (
        id               SERIAL PRIMARY KEY,
        deposito_id      INTEGER NOT NULL REFERENCES depositos(id),
        fecha            DATE NOT NULL,
        proveedor        TEXT NOT NULL,
        tipo_combustible TEXT NOT NULL,
        litros_factura   NUMERIC(14,2) NOT NULL DEFAULT 0,
        litros_recibidos NUMERIC(14,2) NOT NULL DEFAULT 0,
        diferencia_l     NUMERIC(14,2) NOT NULL DEFAULT 0,
        no_vale          TEXT,
        calidad_ok       INTEGER NOT NULL DEFAULT 1,
        observaciones    TEXT,
        responsable_id   INTEGER NOT NULL REFERENCES usuarios(id),
        estado           TEXT NOT NULL DEFAULT 'pendiente',
        created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS transferencias (
        id                    SERIAL PRIMARY KEY,
        deposito_origen_id    INTEGER NOT NULL REFERENCES depositos(id),
        gasolinera_destino_id INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible      TEXT NOT NULL,
        litros_solicitados    NUMERIC(14,2) NOT NULL DEFAULT 0,
        litros_recibidos      NUMERIC(14,2),
        fecha_salida          DATE NOT NULL,
        fecha_llegada         DATE,
        pipa_chapa            TEXT,
        chofer_pipa           TEXT,
        no_documento          TEXT,
        observaciones         TEXT,
        responsable_id        INTEGER NOT NULL REFERENCES usuarios(id),
        estado                TEXT NOT NULL DEFAULT 'en_transito',
        created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── seed: admin ───────────────────────────────────────────────────────────
    cur.execute("SELECT id FROM usuarios WHERE email = %s", ("admin@mercatoria.com",))
    if not cur.fetchone():
        hash_pw = bcrypt.generate_password_hash("Mercatoria2026!").decode("utf-8")
        cur.execute(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
            ("Administrador", "admin@mercatoria.com", hash_pw, "admin")
        )

    # ── seed: clientes ────────────────────────────────────────────────────────
    clientes_seed = [
        ("Programa Mundial de Alimentos", "PMA-001",  "internacional"),
        ("UNFPA",                          "UNFPA-001", "internacional"),
        ("Caritas Cuba",                   "CAR-001",  "nacional"),
        ("SEISA",                          "SEI-001",  "nacional"),
        ("Mercatoria Interna",             "MER-INT",  "interno"),
    ]
    for nombre, codigo, tipo in clientes_seed:
        cur.execute("SELECT id FROM clientes WHERE codigo = %s", (codigo,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO clientes (nombre, codigo, tipo) VALUES (%s, %s, %s)",
                (nombre, codigo, tipo)
            )

    conn.commit()
    cur.close()
    conn.close()
    print("[migraciones_pg] Migraciones PostgreSQL completadas.")
