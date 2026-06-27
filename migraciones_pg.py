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

    # Verificación ligera: si usuarios ya existe, aplicar solo incrementales
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'usuarios'
    """)
    if cur.fetchone()[0] > 0:
        cur.execute("SELECT id FROM usuarios WHERE email = %s", ("admin@mercatoria.com",))
        if not cur.fetchone():
            from flask_bcrypt import Bcrypt as _Bcrypt
            _b = _Bcrypt()
            hash_pw = _b.generate_password_hash("Mercatoria2026!").decode("utf-8")
            cur.execute(
                "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
                ("Administrador", "admin@mercatoria.com", hash_pw, "admin")
            )
            conn.commit()
        conn.close()
        print("[migraciones_pg] Schema existente — migraciones incrementales aplicadas.")
        return

    print("[migraciones_pg] Schema nuevo — ejecutando migraciones completas.")

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

    cur.execute("SELECT id FROM usuarios WHERE email = %s", ("admin@mercatoria.com",))
    if not cur.fetchone():
        hash_pw = bcrypt.generate_password_hash("Mercatoria2026!").decode("utf-8")
        cur.execute(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
            ("Administrador", "admin@mercatoria.com", hash_pw, "admin")
        )

    conn.commit()
    cur.close()
    conn.close()
    print("[migraciones_pg] Migraciones PostgreSQL completadas.")
