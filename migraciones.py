import sqlite3

DATABASE_NAME = "fuel.db"


def _conectar():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _tabla_existe(cursor, tabla):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    )
    return cursor.fetchone() is not None


def _columna_existe(cursor, tabla, columna):
    cursor.execute(f"PRAGMA table_info({tabla})")
    return any(row["name"] == columna for row in cursor.fetchall())


def ejecutar_migraciones(bcrypt):
    conn = _conectar()
    cur = conn.cursor()

    # ── usuarios ───────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre     TEXT NOT NULL,
        email      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rol        TEXT NOT NULL DEFAULT 'operario',
        activo     INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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
        created_at         TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
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
        created_at        TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """)

    # ── movimientos ───────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos (
        id                       INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo                     TEXT NOT NULL,
        fecha                    TEXT NOT NULL DEFAULT (datetime('now')),
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
        created_at               TEXT NOT NULL DEFAULT (datetime('now'))
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
        fecha           TEXT NOT NULL DEFAULT (datetime('now'))
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

    conn.commit()
    conn.close()
    print("[migraciones] SQLite — tablas creadas correctamente.")
