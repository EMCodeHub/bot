import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
from dotenv import load_dotenv
from psycopg2 import ProgrammingError
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
if not ENV_PATH.exists():
    ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ENV_PATH, encoding="utf-8")


def _env_var(name: str) -> str | None:
    """Try DB_* first, then fall back to POSTGRES_* to keep compatibility."""
    value = os.getenv(name)
    if value:
        return value
    legacy = name.replace("DB_", "POSTGRES_")
    return os.getenv(legacy)


def _validate_required_env() -> dict[str, str]:
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    values: dict[str, str] = {}
    for var in required:
        value = _env_var(var)
        if not value:
            raise RuntimeError(f"Missing environment variable: {var}")
        values[var] = value
    return values


def get_connection() -> psycopg2.extensions.connection:
    cfg = _validate_required_env()
    conn = psycopg2.connect(
        host=cfg["DB_HOST"],
        port=int(cfg["DB_PORT"]),
        dbname=cfg["DB_NAME"],
        user=cfg["DB_USER"],
        password=cfg["DB_PASSWORD"],
        options="-c client_encoding=UTF8",
    )
    try:
        register_vector(conn)
    except ProgrammingError:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        register_vector(conn)
    return conn


@contextmanager
def get_cursor(cursor_factory=RealDictCursor) -> Generator[tuple[psycopg2.extensions.connection, psycopg2.extensions.cursor], None, None]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=cursor_factory)
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
