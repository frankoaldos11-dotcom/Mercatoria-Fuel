import os
import sqlite3

from db_config import USE_POSTGRES

DATABASE_NAME = "fuel.db"


class CursorWrapper:
    """Traduce ? a %s automáticamente cuando se usa PostgreSQL."""
    def __init__(self, cursor, use_postgres=False):
        self._cursor = cursor
        self._use_postgres = use_postgres

    def execute(self, sql, params=None):
        if self._use_postgres:
            sql = sql.replace("?", "%s")
        if params is not None:
            return self._cursor.execute(sql, params)
        return self._cursor.execute(sql)

    def executemany(self, sql, params):
        if self._use_postgres:
            sql = sql.replace("?", "%s")
        return self._cursor.executemany(sql, params)

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        if self._use_postgres:
            try:
                self._cursor.execute("SELECT lastval()")
                row = self._cursor.fetchone()
                if row:
                    return row[0] if not hasattr(row, 'keys') else row['lastval']
            except Exception:
                pass
        return self._cursor.lastrowid

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def __iter__(self):
        return iter(self._cursor)


class ConexionWrapper:
    """Wrapper de conexión que devuelve CursorWrapper en lugar del cursor nativo."""
    def __init__(self, conn, use_postgres=False):
        self._conn = conn
        self._use_postgres = use_postgres

    def cursor(self):
        return CursorWrapper(self._conn.cursor(), self._use_postgres)

    def commit(self):
        return self._conn.commit()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._conn.__exit__(*args)


def conectar():
    if USE_POSTGRES:
        from database_pg import conectar_pg
        conn = conectar_pg()
        return ConexionWrapper(conn, use_postgres=True)
    else:
        conexion = sqlite3.connect(DATABASE_NAME)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        return ConexionWrapper(conexion, use_postgres=False)


def columna_existe(cur, tabla, columna):
    """True si `columna` existe hoy en `tabla`, sobre el cursor del llamador.
    Dialect-aware: Postgres consulta information_schema, SQLite usa PRAGMA
    table_info. Pensado para que un caller pueda protegerse antes de leer o
    escribir una columna que podría haber sido eliminada (ej. una barrera de
    seguridad que corre después de un DROP COLUMN ya ejecutado)."""
    if USE_POSTGRES:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = ? AND column_name = ?",
            (tabla, columna),
        )
        return cur.fetchone() is not None
    else:
        cur.execute(f"PRAGMA table_info({tabla})")
        columnas_actuales = [row["name"] for row in cur.fetchall()]
        return columna in columnas_actuales


def tabla_existe(cur, tabla):
    """True si `tabla` existe hoy en el esquema, sobre el cursor del llamador.
    Dialect-aware, mismo criterio que columna_existe() — pensado para que una
    barrera de seguridad pueda chequear datos de una tabla que podría ya
    haber sido eliminada (ejecución idempotente de un DROP TABLE)."""
    if USE_POSTGRES:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            (tabla,),
        )
        return cur.fetchone() is not None
    else:
        cur.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (tabla,))
        return cur.fetchone() is not None


def eliminar_columna_si_existe(cur, tabla, columna):
    """DROP COLUMN idempotente, sobre el cursor/transacción del llamador (sin
    conectar() propio, sin commit propio).

    En Postgres usa `DROP COLUMN IF EXISTS` nativo. SQLite soporta DROP COLUMN
    (desde 3.35+) pero NO la cláusula IF EXISTS para esa sentencia — por eso
    acá se usa columna_existe() primero y solo se intenta el DROP si la
    columna sigue presente. A propósito no se envuelve en un try/except que
    trague cualquier error (patrón que sí usa el proyecto para ADD COLUMN):
    para un DROP, un error real (tabla bloqueada, permisos, etc.) debe
    propagarse, no quedar indistinguible de "ya estaba borrada".
    """
    if USE_POSTGRES:
        cur.execute(f"ALTER TABLE {tabla} DROP COLUMN IF EXISTS {columna}")
    else:
        if columna_existe(cur, tabla, columna):
            cur.execute(f"ALTER TABLE {tabla} DROP COLUMN {columna}")
