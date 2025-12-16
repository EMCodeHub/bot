import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg2
from dotenv import load_dotenv
from psycopg2 import OperationalError, ProgrammingError
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
    legacy_mapping = {
        "DB_HOST": "POSTGRES_HOST",
        "DB_PORT": "POSTGRES_PORT",
        "DB_NAME": "POSTGRES_DB",
        "DB_USER": "POSTGRES_USER",
        "DB_PASSWORD": "POSTGRES_PASSWORD",
    }
    legacy = legacy_mapping.get(name)
    if legacy:
        return os.getenv(legacy)
    return None


def _get_retry_settings() -> tuple[int, float]:
    """Allow deployments to tune how aggressively we wait for Postgres."""
    retries = 10
    delay = 2.0
    try:
        retries = int(os.getenv("DB_CONN_RETRIES", str(retries)))
    except ValueError:
        pass
    try:
        delay = float(os.getenv("DB_CONN_RETRY_DELAY", str(delay)))
    except ValueError:
        pass
    return (max(1, retries), max(0.0, delay))


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
    max_retries, retry_delay = _get_retry_settings()
    last_error: OperationalError | None = None
    conn: psycopg2.extensions.connection | None = None
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=cfg["DB_HOST"],
                port=int(cfg["DB_PORT"]),
                dbname=cfg["DB_NAME"],
                user=cfg["DB_USER"],
                password=cfg["DB_PASSWORD"],
                options="-c client_encoding=UTF8",
            )
            break
        except OperationalError as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            time.sleep(retry_delay)
    if conn is None:
        raise last_error or RuntimeError("Failed to connect to the database.")
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
