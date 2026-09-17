from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.settings import settings

# psycopg.connect() speaks libpq URIs; strip the SQLAlchemy "+psycopg" driver marker.
_PSYCOPG_DSN = settings.database_url.replace(
    "postgresql+psycopg://", "postgresql://", 1
)


def check_db() -> bool:
    try:
        with (
            psycopg.connect(_PSYCOPG_DSN, connect_timeout=3) as conn,
            conn.cursor() as cur,
        ):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception:  # noqa: BLE001 — health check must never raise
        return False


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_PSYCOPG_DSN, row_factory=dict_row) as conn:
        yield conn
