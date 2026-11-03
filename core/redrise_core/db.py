"""Database access: connections for the app role and ordered migrations
(P05-D3, P05-D12)."""

from __future__ import annotations

import contextlib
import threading
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

DBNAME = "redrise"
APP_ROLE = "redrise_app"
MIGRATIONS = Path(__file__).with_name("migrations")


def conninfo(port: int, user: str, password: str, dbname: str = DBNAME) -> str:
    return make_conninfo(host="127.0.0.1", port=port, user=user, password=password, dbname=dbname,
                                          connect_timeout=10, application_name="redrise-core")


def pending_migrations(conn) -> list[Path]:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    return [p for p in sorted(MIGRATIONS.glob("*.sql")) if p.name not in done]


def provision(port: int, superuser: str, su_password: str, app_password: str) -> list[str]:
    """Creates the database and app role if absent and applies pending
    migrations as the owner. Returns the applied migration names."""
    with psycopg.connect(conninfo(port, superuser, su_password, "postgres"), autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DBNAME,)).fetchone():
            c.execute(f"CREATE DATABASE {DBNAME} ENCODING 'UTF8'")
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_ROLE,)).fetchone():
            c.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(APP_ROLE), sql.Literal(app_password)))
        else:
            c.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(APP_ROLE), sql.Literal(app_password)))
    applied = []
    with psycopg.connect(conninfo(port, superuser, su_password)) as c:
        for m in pending_migrations(c):
            with c.transaction():
                c.execute(m.read_text(encoding="utf-8"))
                c.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (m.name,))
            applied.append(m.name)
        # DML only for the app role (no DDL, no superuser).
        c.execute(f"GRANT CONNECT ON DATABASE {DBNAME} TO {APP_ROLE}")
        c.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        c.execute(f"REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        c.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}")
        c.execute(f"REVOKE INSERT, UPDATE, DELETE ON schema_migrations FROM {APP_ROLE}")
        c.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE}")
        c.commit()
    return applied


class Database:
    """Small thread-safe pool for the app role."""

    def __init__(self, info: str, size: int = 8):
        self.info, self.size = info, size
        self._free: list[psycopg.Connection] = []
        self._lock = threading.Lock()

    @contextlib.contextmanager
    def tx(self):
        with self._lock:
            conn = self._free.pop() if self._free else None
        if conn is None or conn.closed:
            conn = psycopg.connect(self.info, row_factory=dict_row)
        try:
            with conn.transaction():
                yield conn
        except psycopg.OperationalError:
            conn.close()
            raise
        finally:
            if not conn.closed:
                with self._lock:
                    if len(self._free) < self.size:
                        self._free.append(conn)
                        conn = None
                if conn is not None:
                    conn.close()

    def close(self):
        with self._lock:
            for c in self._free:
                c.close()
            self._free.clear()
