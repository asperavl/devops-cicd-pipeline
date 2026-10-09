from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def setup_database() -> Generator[None, None, None]:
    """Initialize database for the test session if reachable."""
    try:
        db.init_db()
    except Exception:
        # Allows running unit tests even if DB is offline
        pass
    yield
    db.close_db()


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    """Clean table contents between tests when database is accessible."""
    yield
    if db.check_db_health():
        try:
            with db.get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("TRUNCATE TABLE orders RESTART IDENTITY;")
                conn.commit()
        except Exception:
            pass


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient."""
    with TestClient(app) as test_client:
        yield test_client
