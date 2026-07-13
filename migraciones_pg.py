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

    # ── FASE 1: SCHEMA ────────────────────────────────────────────────────────
    # Todos los CREATE TABLE en orden de dependencias, luego todos los ALTER TABLE.
    # conn.commit() al final garantiza que el esquema está commitado antes de cualquier seed.

    # Tablas raíz (sin FK entre sí)
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
    CREATE TABLE IF NOT EXISTS puertos (
        id         SERIAL PRIMARY KEY,
        nombre     TEXT NOT NULL,
        region     TEXT NOT NULL,
        activo     INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS configuracion (
        clave      TEXT PRIMARY KEY,
        valor      TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # usuarios: gasolinera_id incluida en CREATE TABLE para que DBs frescas la tengan desde el inicio
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id            SERIAL PRIMARY KEY,
        nombre        TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        rol           TEXT NOT NULL DEFAULT 'puesto_de_mando',
        activo        INTEGER NOT NULL DEFAULT 1,
        gasolinera_id INTEGER REFERENCES gasolineras(id),
        created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Nivel 1: dependen solo de tablas raíz
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
    CREATE TABLE IF NOT EXISTS tarjetas (
        id               SERIAL PRIMARY KEY,
        numero_completo  TEXT UNIQUE NOT NULL,
        numero_parcial   TEXT NOT NULL,
        pin_hash         TEXT NOT NULL,
        gasolinera_id    INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible TEXT NOT NULL,
        saldo_usable_l   NUMERIC(14,2) NOT NULL DEFAULT 0,
        saldo_retenido_l NUMERIC(14,2) NOT NULL DEFAULT 0,
        estado           TEXT NOT NULL DEFAULT 'activa',
        notas            TEXT,
        created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS precios_combustible (
        id                   SERIAL PRIMARY KEY,
        gasolinera_id        INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible     TEXT NOT NULL,
        precio_usd_por_litro NUMERIC(10,4) NOT NULL DEFAULT 0,
        activo               INTEGER NOT NULL DEFAULT 1,
        updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(gasolinera_id, tipo_combustible)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS capacidades_gasolinera (
        id                     SERIAL PRIMARY KEY,
        gasolinera_id          INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible       TEXT NOT NULL,
        capacidad_referencia_l NUMERIC(14,2) NOT NULL DEFAULT 0,
        updated_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(gasolinera_id, tipo_combustible)
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

    # Nivel 2: dependen de usuarios + otras
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
    CREATE TABLE IF NOT EXISTS movimientos_tl38 (
        id             SERIAL PRIMARY KEY,
        fecha          DATE NOT NULL,
        gasolinera_id  INTEGER REFERENCES gasolineras(id),
        tipo           TEXT NOT NULL DEFAULT 'despacho',
        chapa          TEXT NOT NULL,
        chofer         TEXT NOT NULL,
        litros         NUMERIC(14,2) NOT NULL DEFAULT 0,
        tarjeta_tl38   TEXT,
        flota          TEXT NOT NULL DEFAULT '599',
        observaciones  TEXT,
        responsable_id INTEGER NOT NULL REFERENCES usuarios(id),
        created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS conciliaciones (
        id                    SERIAL PRIMARY KEY,
        gasolinera_id         INTEGER NOT NULL REFERENCES gasolineras(id),
        fecha                 DATE NOT NULL,
        turno                 TEXT,
        saldo_fisico_inicio_l NUMERIC(14,2) NOT NULL DEFAULT 0,
        saldo_fisico_fin_l    NUMERIC(14,2) NOT NULL DEFAULT 0,
        total_entrada_l       NUMERIC(14,2) NOT NULL DEFAULT 0,
        total_despachado_l    NUMERIC(14,2) NOT NULL DEFAULT 0,
        diferencia_l          NUMERIC(14,2) NOT NULL DEFAULT 0,
        diferencia_porcentaje NUMERIC(8,4) NOT NULL DEFAULT 0,
        estado                TEXT NOT NULL DEFAULT 'borrador',
        observaciones         TEXT,
        responsable_id        INTEGER NOT NULL REFERENCES usuarios(id),
        created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS cliente_usuarios (
        id         SERIAL PRIMARY KEY,
        cliente_id INTEGER NOT NULL REFERENCES clientes(id),
        usuario_id INTEGER NOT NULL UNIQUE REFERENCES usuarios(id),
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reservas_tienda (
        id                   SERIAL PRIMARY KEY,
        usuario_id           INTEGER NOT NULL REFERENCES usuarios(id),
        gasolinera_id        INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible     TEXT NOT NULL,
        litros_solicitados   NUMERIC(14,2) NOT NULL DEFAULT 0,
        precio_usd_por_litro NUMERIC(10,4) NOT NULL DEFAULT 0,
        precio_total_usd     NUMERIC(14,2) NOT NULL DEFAULT 0,
        descripcion_vehiculo TEXT,
        observaciones        TEXT,
        estado               TEXT NOT NULL DEFAULT 'pendiente',
        qr_token             TEXT UNIQUE,
        qr_imagen_b64        TEXT,
        aprobado_por         INTEGER REFERENCES usuarios(id),
        created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehiculos_tienda (
        id               SERIAL PRIMARY KEY,
        usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
        placa            TEXT NOT NULL,
        marca            TEXT,
        modelo           TEXT,
        anio             INTEGER,
        color            TEXT,
        tipo_combustible TEXT,
        activo           INTEGER NOT NULL DEFAULT 1,
        created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(usuario_id, placa)
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recargas_tarjetas (
        id                SERIAL PRIMARY KEY,
        tarjeta_id        INTEGER NOT NULL REFERENCES tarjetas(id),
        fecha             DATE NOT NULL,
        litros_recargados NUMERIC(14,2) NOT NULL DEFAULT 0,
        responsable_id    INTEGER NOT NULL REFERENCES usuarios(id),
        observaciones     TEXT,
        estado            TEXT NOT NULL DEFAULT 'confirmada',
        created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS devoluciones_tarjetas (
        id                        SERIAL PRIMARY KEY,
        tarjeta_id                INTEGER NOT NULL REFERENCES tarjetas(id),
        fecha_incidente           DATE NOT NULL,
        litros_retenidos          NUMERIC(14,2) NOT NULL DEFAULT 0,
        slip_inicial              TEXT,
        slip_devolucion           TEXT,
        slip_restante             TEXT,
        fecha_estimada_liberacion DATE,
        fecha_liberacion_real     DATE,
        estado                    TEXT NOT NULL DEFAULT 'pendiente',
        observaciones             TEXT,
        responsable_id            INTEGER NOT NULL REFERENCES usuarios(id),
        created_at                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at                TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS llegadas_puerto (
        id                  SERIAL PRIMARY KEY,
        puerto_id           INTEGER NOT NULL REFERENCES puertos(id),
        numero_isotanque    TEXT NOT NULL,
        tipo_combustible    TEXT NOT NULL,
        litros              NUMERIC(14,2) NOT NULL DEFAULT 0,
        fecha_llegada       DATE NOT NULL,
        deposito_destino_id INTEGER REFERENCES depositos(id),
        fecha_transferencia DATE,
        estado              TEXT NOT NULL DEFAULT 'en_puerto',
        observaciones       TEXT,
        responsable_id      INTEGER NOT NULL REFERENCES usuarios(id),
        created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    # Nivel 3: dependen de habilitaciones y vehiculos
    cur.execute("""
    CREATE TABLE IF NOT EXISTS habilitaciones (
        id                 SERIAL PRIMARY KEY,
        cliente_id         INTEGER NOT NULL REFERENCES clientes(id),
        unidad_id          INTEGER NOT NULL REFERENCES vehiculos(id),
        gasolinera_id      INTEGER NOT NULL REFERENCES gasolineras(id),
        tarjeta_id         INTEGER NOT NULL REFERENCES tarjetas(id),
        subinventario_id   INTEGER REFERENCES subinventarios(id),
        litros_autorizados NUMERIC(14,2) NOT NULL DEFAULT 0,
        litros_despachados NUMERIC(14,2) NOT NULL DEFAULT 0,
        fecha_habilitacion DATE NOT NULL,
        fecha_vencimiento  DATE,
        estado             TEXT NOT NULL DEFAULT 'pendiente',
        observaciones      TEXT,
        creado_por         INTEGER NOT NULL REFERENCES usuarios(id),
        aprobado_por       INTEGER REFERENCES usuarios(id),
        created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS despachos (
        id                 SERIAL PRIMARY KEY,
        habilitacion_id    INTEGER NOT NULL UNIQUE REFERENCES habilitaciones(id),
        gasolinera_id      INTEGER NOT NULL REFERENCES gasolineras(id),
        tarjeta_id         INTEGER NOT NULL REFERENCES tarjetas(id),
        cliente_id         INTEGER NOT NULL REFERENCES clientes(id),
        unidad_id          INTEGER NOT NULL REFERENCES vehiculos(id),
        litros_despachados NUMERIC(14,2) NOT NULL DEFAULT 0,
        foto_ticket_url    TEXT,
        foto_vehiculo_url  TEXT,
        foto_odometro_url  TEXT,
        odometro_km        INTEGER,
        observaciones      TEXT,
        fecha_despacho     TIMESTAMP NOT NULL,
        operario_id        INTEGER NOT NULL REFERENCES usuarios(id),
        estado             TEXT NOT NULL DEFAULT 'completado',
        created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ── ALTER TABLE: safety net para DBs existentes con esquema parcial ───────
    cur.execute("ALTER TABLE gasolineras ADD COLUMN IF NOT EXISTS provincia TEXT")
    cur.execute("ALTER TABLE movimientos ADD COLUMN IF NOT EXISTS tipo_combustible TEXT")
    cur.execute("ALTER TABLE vehiculos ADD COLUMN IF NOT EXISTS chofer_id INTEGER REFERENCES choferes(id)")
    cur.execute("ALTER TABLE reservas_tienda ADD COLUMN IF NOT EXISTS tarjeta_id INTEGER REFERENCES tarjetas(id)")
    cur.execute("ALTER TABLE reservas_tienda ADD COLUMN IF NOT EXISTS motivo_cancelacion TEXT")
    cur.execute("ALTER TABLE reservas_tienda ADD COLUMN IF NOT EXISTS vehiculo_id INTEGER REFERENCES vehiculos_tienda(id)")
    cur.execute("ALTER TABLE reservas_tienda ADD COLUMN IF NOT EXISTS foto_ticket_url TEXT")
    cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS gasolinera_id INTEGER REFERENCES gasolineras(id)")
    cur.execute("ALTER TABLE transferencias ADD COLUMN IF NOT EXISTS litros_distribuidos NUMERIC(14,2) DEFAULT 0")
    cur.execute("ALTER TABLE tarjetas ADD COLUMN IF NOT EXISTS saldo_usd NUMERIC(14,2) NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verificado INTEGER NOT NULL DEFAULT 0")
    cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_token_hash TEXT")
    cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_codigo_hash TEXT")
    cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS verificacion_expira TIMESTAMP")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_saldo_fincimex (
        id             SERIAL PRIMARY KEY,
        tipo           TEXT NOT NULL,
        monto_usd      NUMERIC(14,2) NOT NULL DEFAULT 0,
        litros         NUMERIC(14,2),
        factor         NUMERIC(10,4),
        recepcion_id   INTEGER REFERENCES recepciones(id),
        tarjeta_id     INTEGER REFERENCES tarjetas(id),
        responsable_id INTEGER NOT NULL REFERENCES usuarios(id),
        observaciones  TEXT,
        created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)


    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes (
        id           SERIAL PRIMARY KEY,
        destinatario TEXT NOT NULL,
        asunto       TEXT NOT NULL,
        cuerpo       TEXT NOT NULL,
        tipo         TEXT NOT NULL DEFAULT 'general',
        estado       TEXT NOT NULL DEFAULT 'enviado',
        error        TEXT,
        usuario_id   INTEGER REFERENCES usuarios(id),
        cliente_id   INTEGER REFERENCES clientes(id),
        created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes_masivos (
        id                             SERIAL PRIMARY KEY,
        asunto                         TEXT NOT NULL,
        cuerpo                         TEXT NOT NULL,
        modo_destinatario              TEXT NOT NULL,
        filtro_estado                  TEXT,
        incluir_inapp                  INTEGER NOT NULL DEFAULT 0,
        estado                         TEXT NOT NULL DEFAULT 'pendiente',
        autor_id                       INTEGER NOT NULL REFERENCES usuarios(id),
        aprobado_por                   INTEGER REFERENCES usuarios(id),
        motivo_rechazo                 TEXT,
        total_destinatarios            INTEGER NOT NULL DEFAULT 0,
        total_enviados                 INTEGER NOT NULL DEFAULT 0,
        total_excluidos_no_verificado  INTEGER NOT NULL DEFAULT 0,
        total_fallidos                 INTEGER NOT NULL DEFAULT 0,
        enviado_at                     TIMESTAMP,
        created_at                     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at                     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes_masivos_destinatarios (
        id         SERIAL PRIMARY KEY,
        masivo_id  INTEGER NOT NULL REFERENCES mensajes_masivos(id),
        usuario_id INTEGER NOT NULL REFERENCES usuarios(id)
    )
    """)

    # Esquema completo garantizado antes de cualquier seed
    conn.commit()
    print("[migraciones_pg] Fase 1 (schema) completada y commitada.")

    # ── FASE 2: SEEDS ─────────────────────────────────────────────────────────
    # Todos idempotentes: SELECT-skip o ON CONFLICT DO NOTHING.

    # seed: admin
    cur.execute("SELECT id FROM usuarios WHERE email = %s", ("admin@mercatoria.com",))
    if not cur.fetchone():
        hash_pw = bcrypt.generate_password_hash("Mercatoria2026!").decode("utf-8")
        cur.execute(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
            ("Administrador", "admin@mercatoria.com", hash_pw, "admin")
        )

    # seed: clientes
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

    # seed: gasolinera La Shell
    cur.execute("SELECT id FROM gasolineras WHERE nombre = %s", ("La Shell",))
    row_shell = cur.fetchone()
    if not row_shell:
        cur.execute("""
            INSERT INTO gasolineras (nombre, region, combustible, capacidad_l, estado)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        """, ("La Shell", "Occidente", "diesel,gasolina_regular,gasolina_especial", 50000, "activo"))
        shell_id = cur.fetchone()[0]
    else:
        shell_id = row_shell[0]

    # seed: usuario cliente PMA
    cur.execute("SELECT id FROM usuarios WHERE email = %s", ("cliente_pma@mercatoria.com",))
    if not cur.fetchone():
        hash_cli = bcrypt.generate_password_hash("Cliente2026!").decode("utf-8")
        cur.execute("""
            INSERT INTO usuarios (nombre, email, password_hash, rol)
            VALUES (%s, %s, %s, %s)
        """, ("Cliente PMA", "cliente_pma@mercatoria.com", hash_cli, "cliente"))
        cur.execute("SELECT id FROM usuarios WHERE email = %s", ("cliente_pma@mercatoria.com",))
        cli_user_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM clientes WHERE codigo = %s", ("PMA-001",))
        pma_row = cur.fetchone()
        if pma_row:
            cur.execute("""
                INSERT INTO cliente_usuarios (cliente_id, usuario_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (pma_row[0], cli_user_id))

    # seed: tarjetas Fincimex + devoluciones
    cur.execute("SELECT id FROM usuarios WHERE email = %s", ("admin@mercatoria.com",))
    row_admin = cur.fetchone()
    admin_id = row_admin[0] if row_admin else 1

    from werkzeug.security import generate_password_hash as _gph
    from datetime import date, timedelta
    pin_seed = _gph("0000")
    fecha_estimada_seed = (date.today() + timedelta(days=10)).isoformat()

    tarjetas_seed = [
        ("0000000000008777", "8777", "diesel", 3200.00,  0.00, False),
        ("0000000000008785", "8785", "diesel", 3200.00,  0.00, False),
        ("0000000000008751", "8751", "diesel",   62.00,  0.00, False),
        ("0000000000000898", "0898", "diesel",    0.07, 566.93, True),
        ("0000000000000880", "0880", "diesel",    4.73,  55.27, True),
    ]
    for num_completo, num_parcial, combustible, saldo_usable, saldo_retenido, tiene_dev in tarjetas_seed:
        cur.execute("SELECT id FROM tarjetas WHERE numero_completo = %s", (num_completo,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO tarjetas
                    (numero_completo, numero_parcial, pin_hash, gasolinera_id,
                     tipo_combustible, saldo_usable_l, saldo_retenido_l, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'activa') RETURNING id
            """, (num_completo, num_parcial, pin_seed, shell_id,
                  combustible, saldo_usable, saldo_retenido))
            nueva_id = cur.fetchone()[0]
            if tiene_dev:
                cur.execute("""
                    INSERT INTO devoluciones_tarjetas
                        (tarjeta_id, fecha_incidente, litros_retenidos, estado,
                         fecha_estimada_liberacion, responsable_id, observaciones)
                    VALUES (%s, CURRENT_DATE, %s, 'pendiente', %s, %s, %s)
                """, (nueva_id, saldo_retenido, fecha_estimada_seed, admin_id,
                      f"Devolución inicial — tarjeta ****{num_parcial}"))

    # seed: puertos
    puertos_seed = [
        ("Puerto Mariel",   "Occidente"),
        ("Puerto Santiago", "Oriente"),
    ]
    for nombre_p, region_p in puertos_seed:
        cur.execute("SELECT id FROM puertos WHERE nombre = %s", (nombre_p,))
        if not cur.fetchone():
            cur.execute("INSERT INTO puertos (nombre, region) VALUES (%s, %s)", (nombre_p, region_p))

    # seed: configuracion
    params_default = [
        ("compra_minima_litros", "500"),
        ("factor_litro_usd", "0.90"),
    ]
    for clave, valor in params_default:
        cur.execute(
            "INSERT INTO configuracion (clave, valor) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (clave, valor)
        )

    conn.commit()
    print("[migraciones_pg] Fase 2 (seeds) completada. Base de datos lista.")
