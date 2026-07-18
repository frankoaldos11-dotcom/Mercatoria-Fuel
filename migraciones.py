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
        rol           TEXT NOT NULL DEFAULT 'puesto_de_mando',
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

    # ── columnas añadidas a gasolineras post-v1 (idempotentes) ───────────────
    for _alter in [
        "ALTER TABLE gasolineras ADD COLUMN provincia TEXT",
    ]:
        try:
            cur.execute(_alter)
        except Exception:
            pass

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

    # ── columnas añadidas a movimientos post-v3 ───────────────────────────────
    try:
        cur.execute("ALTER TABLE movimientos ADD COLUMN tipo_combustible TEXT")
    except Exception:
        pass

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

    # ── columnas añadidas a vehiculos post-v2 (idempotentes) ─────────────────
    for _alter in [
        "ALTER TABLE vehiculos ADD COLUMN chofer_id INTEGER REFERENCES choferes(id)",
    ]:
        try:
            cur.execute(_alter)
        except Exception:
            pass

    # ── depositos ─────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS depositos (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre           TEXT NOT NULL,
        region           TEXT NOT NULL,
        direccion        TEXT,
        tipo_combustible TEXT NOT NULL,
        capacidad_l      REAL NOT NULL DEFAULT 0,
        responsable      TEXT,
        notas            TEXT,
        estado           TEXT NOT NULL DEFAULT 'activo',
        created_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── recepciones ───────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recepciones (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        deposito_id      INTEGER NOT NULL REFERENCES depositos(id),
        fecha            TEXT NOT NULL,
        proveedor        TEXT NOT NULL,
        tipo_combustible TEXT NOT NULL,
        litros_factura   REAL NOT NULL DEFAULT 0,
        litros_recibidos REAL NOT NULL DEFAULT 0,
        diferencia_l     REAL NOT NULL DEFAULT 0,
        no_vale          TEXT,
        calidad_ok       INTEGER NOT NULL DEFAULT 1,
        observaciones    TEXT,
        responsable_id   INTEGER NOT NULL REFERENCES usuarios(id),
        estado           TEXT NOT NULL DEFAULT 'pendiente',
        created_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── transferencias ────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transferencias (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        deposito_origen_id    INTEGER NOT NULL REFERENCES depositos(id),
        gasolinera_destino_id INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible      TEXT NOT NULL,
        litros_solicitados    REAL NOT NULL DEFAULT 0,
        litros_recibidos      REAL,
        fecha_salida          TEXT NOT NULL,
        fecha_llegada         TEXT,
        pipa_chapa            TEXT,
        chofer_pipa           TEXT,
        no_documento          TEXT,
        observaciones         TEXT,
        responsable_id        INTEGER NOT NULL REFERENCES usuarios(id),
        estado                TEXT NOT NULL DEFAULT 'en_transito',
        created_at            TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at            TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── tarjetas ──────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tarjetas (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_completo  TEXT UNIQUE NOT NULL,
        numero_parcial   TEXT NOT NULL,
        pin_hash         TEXT NOT NULL,
        gasolinera_id    INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible TEXT NOT NULL,
        saldo_usable_l   REAL NOT NULL DEFAULT 0,
        saldo_retenido_l REAL NOT NULL DEFAULT 0,
        estado           TEXT NOT NULL DEFAULT 'activa',
        notas            TEXT,
        created_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── recargas_tarjetas ─────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS recargas_tarjetas (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        tarjeta_id        INTEGER NOT NULL REFERENCES tarjetas(id),
        fecha             TEXT NOT NULL,
        litros_recargados REAL NOT NULL DEFAULT 0,
        responsable_id    INTEGER NOT NULL REFERENCES usuarios(id),
        observaciones     TEXT,
        estado            TEXT NOT NULL DEFAULT 'confirmada',
        created_at        TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at        TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── devoluciones_tarjetas ─────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS devoluciones_tarjetas (
        id                        INTEGER PRIMARY KEY AUTOINCREMENT,
        tarjeta_id                INTEGER NOT NULL REFERENCES tarjetas(id),
        fecha_incidente           TEXT NOT NULL,
        litros_retenidos          REAL NOT NULL DEFAULT 0,
        slip_inicial              TEXT,
        slip_devolucion           TEXT,
        slip_restante             TEXT,
        fecha_estimada_liberacion TEXT,
        fecha_liberacion_real     TEXT,
        estado                    TEXT NOT NULL DEFAULT 'pendiente',
        observaciones             TEXT,
        responsable_id            INTEGER NOT NULL REFERENCES usuarios(id),
        created_at                TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at                TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── habilitaciones ────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS habilitaciones (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id         INTEGER NOT NULL REFERENCES clientes(id),
        unidad_id          INTEGER NOT NULL REFERENCES vehiculos(id),
        gasolinera_id      INTEGER NOT NULL REFERENCES gasolineras(id),
        tarjeta_id         INTEGER NOT NULL REFERENCES tarjetas(id),
        subinventario_id   INTEGER REFERENCES subinventarios(id),
        litros_autorizados REAL NOT NULL DEFAULT 0,
        litros_despachados REAL NOT NULL DEFAULT 0,
        fecha_habilitacion TEXT NOT NULL,
        fecha_vencimiento  TEXT,
        estado             TEXT NOT NULL DEFAULT 'pendiente',
        observaciones      TEXT,
        creado_por         INTEGER NOT NULL REFERENCES usuarios(id),
        aprobado_por       INTEGER REFERENCES usuarios(id),
        created_at         TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at         TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── despachos ─────────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS despachos (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        habilitacion_id    INTEGER NOT NULL UNIQUE REFERENCES habilitaciones(id),
        gasolinera_id      INTEGER NOT NULL REFERENCES gasolineras(id),
        tarjeta_id         INTEGER NOT NULL REFERENCES tarjetas(id),
        cliente_id         INTEGER NOT NULL REFERENCES clientes(id),
        unidad_id          INTEGER NOT NULL REFERENCES vehiculos(id),
        litros_despachados REAL NOT NULL DEFAULT 0,
        foto_ticket_url    TEXT,
        foto_vehiculo_url  TEXT,
        foto_odometro_url  TEXT,
        odometro_km        INTEGER,
        observaciones      TEXT,
        fecha_despacho     TEXT NOT NULL,
        operario_id        INTEGER NOT NULL REFERENCES usuarios(id),
        estado             TEXT NOT NULL DEFAULT 'completado',
        created_at         TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at         TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── adjuntos ──────────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS adjuntos (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        origen_tipo      TEXT NOT NULL,
        origen_id        INTEGER NOT NULL,
        categoria        TEXT NOT NULL,
        nombre_original  TEXT,
        mime_type        TEXT NOT NULL,
        contenido        BLOB NOT NULL,
        created_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_adjuntos_origen ON adjuntos (origen_tipo, origen_id)
    """)

    # ── conciliaciones ────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS conciliaciones (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        gasolinera_id         INTEGER NOT NULL REFERENCES gasolineras(id),
        fecha                 TEXT NOT NULL,
        turno                 TEXT,
        saldo_fisico_inicio_l REAL NOT NULL DEFAULT 0,
        saldo_fisico_fin_l    REAL NOT NULL DEFAULT 0,
        total_entrada_l       REAL NOT NULL DEFAULT 0,
        total_despachado_l    REAL NOT NULL DEFAULT 0,
        diferencia_l          REAL NOT NULL DEFAULT 0,
        diferencia_porcentaje REAL NOT NULL DEFAULT 0,
        estado                TEXT NOT NULL DEFAULT 'borrador',
        observaciones         TEXT,
        responsable_id        INTEGER NOT NULL REFERENCES usuarios(id),
        created_at            TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at            TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── cliente_usuarios ─────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cliente_usuarios (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL REFERENCES clientes(id),
        usuario_id INTEGER NOT NULL UNIQUE REFERENCES usuarios(id),
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── movimientos_tl38 ─────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_tl38 (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha          TEXT NOT NULL,
        gasolinera_id  INTEGER REFERENCES gasolineras(id),
        tipo           TEXT NOT NULL DEFAULT 'despacho',
        chapa          TEXT NOT NULL,
        chofer         TEXT NOT NULL,
        litros         REAL NOT NULL DEFAULT 0,
        tarjeta_tl38   TEXT,
        flota          TEXT NOT NULL DEFAULT '599',
        observaciones  TEXT,
        responsable_id INTEGER NOT NULL REFERENCES usuarios(id),
        created_at     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── puertos ───────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS puertos (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre     TEXT NOT NULL,
        region     TEXT NOT NULL,
        activo     INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── llegadas_puerto ───────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS llegadas_puerto (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        puerto_id           INTEGER NOT NULL REFERENCES puertos(id),
        numero_isotanque    TEXT NOT NULL,
        tipo_combustible    TEXT NOT NULL,
        litros              REAL NOT NULL DEFAULT 0,
        fecha_llegada       TEXT NOT NULL,
        deposito_destino_id INTEGER REFERENCES depositos(id),
        fecha_transferencia TEXT,
        estado              TEXT NOT NULL DEFAULT 'en_puerto',
        observaciones       TEXT,
        responsable_id      INTEGER NOT NULL REFERENCES usuarios(id),
        created_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at          TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── configuracion ────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS configuracion (
        clave      TEXT PRIMARY KEY,
        valor      TEXT NOT NULL,
        updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)


    # ── mensajes ─────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        destinatario TEXT NOT NULL,
        asunto       TEXT NOT NULL,
        cuerpo       TEXT NOT NULL,
        tipo         TEXT NOT NULL DEFAULT 'general',
        estado       TEXT NOT NULL DEFAULT 'enviado',
        error        TEXT,
        usuario_id   INTEGER REFERENCES usuarios(id),
        cliente_id   INTEGER REFERENCES clientes(id),
        created_at   TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── mensajes_masivos ─────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes_masivos (
        id                             INTEGER PRIMARY KEY AUTOINCREMENT,
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
        enviado_at                     TEXT,
        created_at                     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at                     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes_masivos_destinatarios (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        masivo_id  INTEGER NOT NULL REFERENCES mensajes_masivos(id),
        usuario_id INTEGER NOT NULL REFERENCES usuarios(id)
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
        ("Programa Mundial de Alimentos", "PMA-001"),
        ("UNFPA",                          "UNFPA-001"),
        ("Caritas Cuba",                   "CAR-001"),
        ("SEISA",                          "SEI-001"),
        ("Mercatoria Interna",             "MER-INT"),
    ]
    for nombre, codigo in clientes_seed:
        cur.execute("SELECT id FROM clientes WHERE codigo = ?", (codigo,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO clientes (nombre, codigo) VALUES (?, ?)",
                (nombre, codigo)
            )

    # ── seed: gasolinera La Shell ─────────────────────────────────────────────
    cur.execute("SELECT id FROM gasolineras WHERE nombre = ?", ("La Shell",))
    row_shell = cur.fetchone()
    if not row_shell:
        cur.execute("""
            INSERT INTO gasolineras (nombre, region, combustible, estado)
            VALUES (?, ?, ?, ?)
        """, ("La Shell", "Occidente", "diesel,gasolina_regular,gasolina_especial", "activo"))
        shell_id = cur.lastrowid
    else:
        shell_id = row_shell["id"]

    # ── seed: usuario cliente PMA ────────────────────────────────────────────
    cur.execute("SELECT id FROM usuarios WHERE email = ?", ("cliente_pma@mercatoria.com",))
    if not cur.fetchone():
        hash_cli = bcrypt.generate_password_hash("Cliente2026!").decode("utf-8")
        cur.execute("""
            INSERT INTO usuarios (nombre, email, password_hash, rol)
            VALUES (?, ?, ?, ?)
        """, ("Cliente PMA", "cliente_pma@mercatoria.com", hash_cli, "cliente"))
        cli_user_id = cur.lastrowid
        cur.execute("SELECT id FROM clientes WHERE codigo = ?", ("PMA-001",))
        pma_row = cur.fetchone()
        if pma_row:
            cur.execute("""
                INSERT OR IGNORE INTO cliente_usuarios (cliente_id, usuario_id)
                VALUES (?, ?)
            """, (pma_row["id"], cli_user_id))

    # ── seed: tarjetas Fincimex ───────────────────────────────────────────────
    cur.execute("SELECT id FROM usuarios WHERE email = ?", ("admin@mercatoria.com",))
    row_admin = cur.fetchone()
    admin_id = row_admin["id"] if row_admin else 1

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
        cur.execute("SELECT id FROM tarjetas WHERE numero_completo = ?", (num_completo,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO tarjetas
                    (numero_completo, numero_parcial, pin_hash, gasolinera_id,
                     tipo_combustible, saldo_usable_l, saldo_retenido_l, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'activa')
            """, (num_completo, num_parcial, pin_seed, shell_id,
                  combustible, saldo_usable, saldo_retenido))
            nueva_id = cur.lastrowid
            if tiene_dev:
                cur.execute("""
                    INSERT INTO devoluciones_tarjetas
                        (tarjeta_id, fecha_incidente, litros_retenidos, estado,
                         fecha_estimada_liberacion, responsable_id, observaciones)
                    VALUES (?, date('now'), ?, 'pendiente', ?, ?, ?)
                """, (nueva_id, saldo_retenido, fecha_estimada_seed, admin_id,
                      f"Devolución inicial — tarjeta ****{num_parcial}"))

    # ── seed: puertos ─────────────────────────────────────────────────────────
    puertos_seed = [
        ("Puerto Mariel",   "Occidente"),
        ("Puerto Santiago", "Oriente"),
    ]
    for nombre_p, region_p in puertos_seed:
        cur.execute("SELECT id FROM puertos WHERE nombre = ?", (nombre_p,))
        if not cur.fetchone():
            cur.execute("INSERT INTO puertos (nombre, region) VALUES (?, ?)", (nombre_p, region_p))

    # ── precios_combustible ───────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS precios_combustible (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        gasolinera_id        INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible     TEXT NOT NULL,
        precio_usd_por_litro REAL NOT NULL DEFAULT 0,
        activo               INTEGER NOT NULL DEFAULT 1,
        updated_at           TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        UNIQUE(gasolinera_id, tipo_combustible)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS capacidades_gasolinera (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        gasolinera_id          INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible       TEXT NOT NULL,
        capacidad_referencia_l REAL NOT NULL DEFAULT 0,
        updated_at             TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        UNIQUE(gasolinera_id, tipo_combustible)
    )
    """)

    # ── reservas_tienda ───────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS reservas_tienda (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id           INTEGER NOT NULL REFERENCES usuarios(id),
        gasolinera_id        INTEGER NOT NULL REFERENCES gasolineras(id),
        tipo_combustible     TEXT NOT NULL,
        litros_solicitados   REAL NOT NULL DEFAULT 0,
        precio_usd_por_litro REAL NOT NULL DEFAULT 0,
        precio_total_usd     REAL NOT NULL DEFAULT 0,
        descripcion_vehiculo TEXT,
        observaciones        TEXT,
        estado               TEXT NOT NULL DEFAULT 'pendiente',
        qr_token             TEXT UNIQUE,
        qr_imagen_b64        TEXT,
        aprobado_por         INTEGER REFERENCES usuarios(id),
        created_at           TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at           TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── vehiculos_tienda ─────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vehiculos_tienda (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
        placa            TEXT NOT NULL,
        marca            TEXT,
        modelo           TEXT,
        anio             INTEGER,
        color            TEXT,
        tipo_combustible TEXT,
        activo           INTEGER NOT NULL DEFAULT 1,
        created_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        updated_at       TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
        UNIQUE(usuario_id, placa)
    )
    """)

    # ── ALTER TABLE ───────────────────────────────────────────────────────────
    for _sql in [
        "ALTER TABLE reservas_tienda ADD COLUMN tarjeta_id INTEGER REFERENCES tarjetas(id)",
        "ALTER TABLE reservas_tienda ADD COLUMN motivo_cancelacion TEXT",
        "ALTER TABLE movimientos_saldo_fincimex ADD COLUMN llegada_puerto_id INTEGER REFERENCES llegadas_puerto(id)",
        "ALTER TABLE reservas_tienda ADD COLUMN vehiculo_id INTEGER REFERENCES vehiculos_tienda(id)",
        "ALTER TABLE reservas_tienda ADD COLUMN foto_ticket_url TEXT",
        "ALTER TABLE usuarios ADD COLUMN gasolinera_id INTEGER REFERENCES gasolineras(id)",
        "ALTER TABLE transferencias ADD COLUMN litros_distribuidos REAL DEFAULT 0",
        # tarjetas.saldo_usd: NO volver a agregar acá — es una de las columnas
        # que elimina el botón de Zona de peligro en /configuracion/. Si esta
        # línea sigue presente, el ADD COLUMN se reintenta en cada arranque y
        # ya no falla por "columna duplicada" una vez que el DROP la borró —
        # resucitaría la columna en cada reinicio, deshaciendo el DROP.
        "ALTER TABLE usuarios ADD COLUMN email_verificado INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE usuarios ADD COLUMN verificacion_token_hash TEXT",
        "ALTER TABLE usuarios ADD COLUMN verificacion_codigo_hash TEXT",
        "ALTER TABLE usuarios ADD COLUMN verificacion_expira TEXT",
        "ALTER TABLE tarjetas ADD COLUMN pin_plano TEXT",
        "ALTER TABLE despachos ADD COLUMN numero_operacion TEXT",
        "ALTER TABLE devoluciones_tarjetas ADD COLUMN destino_liberacion TEXT",
        "ALTER TABLE devoluciones_tarjetas ADD COLUMN motivo_perdida TEXT",
        "ALTER TABLE llegadas_puerto ADD COLUMN litros_recibidos REAL",
        "ALTER TABLE llegadas_puerto ADD COLUMN merma_l REAL",
        "ALTER TABLE llegadas_puerto ADD COLUMN bolson_generado_por TEXT",
        "ALTER TABLE llegadas_puerto ADD COLUMN bolson_forzado_motivo TEXT",
        "ALTER TABLE llegadas_puerto ADD COLUMN bolson_forzado_por INTEGER REFERENCES usuarios(id)",
        "ALTER TABLE clientes ADD COLUMN nit TEXT",
        "ALTER TABLE clientes ADD COLUMN direccion TEXT",
        "ALTER TABLE despachos ADD COLUMN tipo_despacho TEXT NOT NULL DEFAULT 'normal'",
        "ALTER TABLE despachos ADD COLUMN motivo_registro_tardio TEXT",
    ]:
        try:
            cur.execute(_sql)
        except Exception:
            pass

    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_despachos_numero_operacion
        ON despachos (numero_operacion)
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movimientos_saldo_fincimex (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo           TEXT NOT NULL,
        monto_usd      REAL NOT NULL DEFAULT 0,
        litros         REAL,
        factor         REAL,
        recepcion_id   INTEGER REFERENCES recepciones(id),
        tarjeta_id     INTEGER REFERENCES tarjetas(id),
        responsable_id INTEGER NOT NULL REFERENCES usuarios(id),
        observaciones  TEXT,
        created_at     TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
    )
    """)

    # ── seed: configuracion ───────────────────────────────────────────────────
    params_default = [
        ("compra_minima_litros", "500"),
        ("factor_litro_usd", "0.90"),
    ]
    for clave, valor in params_default:
        cur.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor))

    conn.commit()
    conn.close()
    print("[migraciones] SQLite — tablas creadas correctamente.")
