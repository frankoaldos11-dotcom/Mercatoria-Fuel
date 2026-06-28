import sqlite3

from database import DATABASE_NAME


def _conectar():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ejecutar_migraciones(bcrypt):
    conn = _conectar()
    cur = conn.cursor()

    # ── usuarios ───────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre        TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rol           TEXT NOT NULL DEFAULT 'operario',
        activo        INTEGER NOT NULL DEFAULT 1,
        created_at    TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at    TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── gasolineras ───────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gasolineras (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre             TEXT NOT NULL,
        region             TEXT NOT NULL,
        direccion          TEXT,
        combustible        TEXT NOT NULL,
        capacidad_l        REAL NOT NULL DEFAULT 0,
        gestor_responsable TEXT,
        estado             TEXT NOT NULL DEFAULT 'activo',
        created_at         TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at         TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── subinventarios ────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subinventarios (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        gasolinera_id     INTEGER NOT NULL REFERENCES gasolineras(id),
        nombre            TEXT NOT NULL,
        tipo              TEXT NOT NULL DEFAULT 'mercatoria_interna',
        orden_prioridad   INTEGER NOT NULL DEFAULT 0,
        litros_reservados REAL NOT NULL DEFAULT 0,
        cliente_id        INTEGER,
        activo            INTEGER NOT NULL DEFAULT 1,
        created_at        TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at        TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── movimientos ───────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo                     TEXT NOT NULL,
        fecha                    TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        gasolinera_id            INTEGER REFERENCES gasolineras(id),
        deposito_id              INTEGER,
        tarjeta_id               INTEGER,
        cliente_id               INTEGER,
        vehiculo_id              INTEGER,
        chofer_id                INTEGER,
        subinventario_origen_id  INTEGER REFERENCES subinventarios(id),
        subinventario_destino_id INTEGER REFERENCES subinventarios(id),
        litros                   REAL NOT NULL DEFAULT 0,
        responsable_id           INTEGER NOT NULL REFERENCES usuarios(id),
        observaciones            TEXT,
        created_at               TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── auditoria ─────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS auditoria (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id      INTEGER REFERENCES usuarios(id),
        accion          TEXT NOT NULL,
        tabla_afectada  TEXT,
        registro_id     INTEGER,
        valor_anterior  TEXT,
        valor_nuevo     TEXT,
        ip              TEXT,
        user_agent      TEXT,
        fecha           TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── clientes ──────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id                        INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre                    TEXT NOT NULL,
        codigo                    TEXT UNIQUE NOT NULL,
        tipo                      TEXT NOT NULL DEFAULT 'internacional',
        contacto_nombre           TEXT,
        contacto_telefono         TEXT,
        contacto_email            TEXT,
        subinventario_reservado_l REAL NOT NULL DEFAULT 0,
        notas                     TEXT,
        activo                    INTEGER NOT NULL DEFAULT 1,
        created_at                TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at                TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── vehiculos ─────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehiculos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id      INTEGER NOT NULL REFERENCES clientes(id),
        chapa           TEXT UNIQUE NOT NULL,
        marca           TEXT,
        modelo          TEXT,
        anio            INTEGER,
        tipo_combustible TEXT NOT NULL,
        cuota_mensual_l REAL,
        color           TEXT,
        observaciones   TEXT,
        estado          TEXT NOT NULL DEFAULT 'activo',
        created_at      TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at      TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── choferes ──────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS choferes (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id           INTEGER NOT NULL REFERENCES clientes(id),
        nombre               TEXT NOT NULL,
        ci                   TEXT UNIQUE NOT NULL,
        licencia_numero      TEXT,
        licencia_vencimiento TEXT,
        telefono             TEXT,
        observaciones        TEXT,
        estado               TEXT NOT NULL DEFAULT 'activo',
        created_at           TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at           TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── seed: admin ───────────────────────────────────────────────────────────
    cur.execute("SELECT id FROM usuarios WHERE email = ?", ("admin@mercatoria.com",))
    if not cur.fetchone():
        hash_pw = bcrypt.generate_password_hash("Mercatoria2026!").decode("utf-8")
        cur.execute("""
            INSERT INTO usuarios (nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?)
        """, ("Administrador", "admin@mercatoria.com", hash_pw, "admin"))

    # ── seed: clientes ────────────────────────────────────────────────────────
    clientes_seed = [
        ("Programa Mundial de Alimentos", "PMA-001",  "internacional"),
        ("UNFPA",                          "UNFPA-001", "internacional"),
        ("Caritas Cuba",                   "CAR-001",  "nacional"),
        ("SEISA",                          "SEI-001",  "nacional"),
        ("Mercatoria Interna",             "MER-INT",  "interno"),
    ]
    for nombre, codigo, tipo in clientes_seed:
        cur.execute("SELECT id FROM clientes WHERE codigo = ?", (codigo,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO clientes (nombre, codigo, tipo) VALUES (?, ?, ?)",
                (nombre, codigo, tipo)
            )

    conn.commit()
    conn.close()
    print("[migraciones] SQLite — tablas creadas correctamente.")
