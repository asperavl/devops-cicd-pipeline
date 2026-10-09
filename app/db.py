import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

logger = logging.getLogger("app.db")

pool: ConnectionPool | None = None

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db() -> None:
    """Initialize database connection pool and ensure table schema exists.

    Implements bounded connection retries with exponential backoff.
    """
    global pool
    retries = settings.DB_CONNECT_RETRIES
    delay = settings.DB_CONNECT_RETRY_DELAY

    for attempt in range(1, retries + 1):
        try:
            logger.info("Connecting to database (attempt %d/%d)...", attempt, retries)
            new_pool = ConnectionPool(
                conninfo=settings.conninfo,
                min_size=1,
                max_size=10,
                kwargs={"row_factory": dict_row},
                open=False,
            )
            new_pool.open(wait=True, timeout=5.0)

            # Initialize schema
            with new_pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(CREATE_TABLE_SQL)
                conn.commit()

            pool = new_pool
            logger.info("Database initialized successfully.")
            return
        except Exception as exc:
            logger.warning("Database connection failed on attempt %d: %s", attempt, exc)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("Exhausted database connection retries.")
                raise


def close_db() -> None:
    """Close connection pool gracefully."""
    global pool
    if pool is not None:
        try:
            pool.close()
            logger.info("Database connection pool closed.")
        except Exception as exc:
            logger.warning("Error closing connection pool: %s", exc)
        finally:
            pool = None


def check_db_health() -> bool:
    """Verify database connectivity with a lightweight ping query."""
    global pool
    if pool is None:
        return False
    try:
        with pool.connection(timeout=2.0) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                return cur.fetchone() is not None
    except Exception:
        return False


@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """Provide a database connection context from the pool."""
    global pool
    if pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    with pool.connection() as conn:
        yield conn
