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
