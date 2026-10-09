from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient


def test_read_root(client: TestClient) -> None:
    """Test root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Order Management API"
    assert data["status"] == "running"


def test_health_healthy(client: TestClient) -> None:
    """Test /health returns 200 when database is healthy."""
    with patch("app.db.check_db_health", return_value=True):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


def test_health_unhealthy(client: TestClient) -> None:
    """Test /health returns 503 when database is disconnected."""
    with patch("app.db.check_db_health", return_value=False):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


def test_create_order_success(client: TestClient) -> None:
    """Test successful order creation."""
    payload = {
        "customer_name": "Alice",
        "item_name": "Mechanical Keyboard",
        "quantity": 2,
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["customer_name"] == "Alice"
    assert data["item_name"] == "Mechanical Keyboard"
    assert data["quantity"] == 2
    assert "created_at" in data


def test_create_order_missing_fields(client: TestClient) -> None:
    """Test validation rejection when required fields are missing."""
    response = client.post("/orders", json={"customer_name": "Alice"})
    assert response.status_code == 422


def test_create_order_invalid_quantity(client: TestClient) -> None:
    """Test validation rejection for non-positive quantity."""
    # Zero quantity
    res_zero = client.post(
        "/orders",
        json={"customer_name": "Alice", "item_name": "Mouse", "quantity": 0},
    )
    assert res_zero.status_code == 422

    # Negative quantity
    res_neg = client.post(
        "/orders",
        json={"customer_name": "Alice", "item_name": "Mouse", "quantity": -5},
    )
    assert res_neg.status_code == 422


def test_list_orders(client: TestClient) -> None:
    """Test listing orders."""
    # Create two orders
    client.post(
        "/orders",
        json={"customer_name": "Bob", "item_name": "Monitor", "quantity": 1},
    )
    client.post(
        "/orders",
        json={"customer_name": "Charlie", "item_name": "Desk Mat", "quantity": 3},
    )

    response = client.get("/orders")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_get_order_by_id_success(client: TestClient) -> None:
    """Test retrieving an existing order by ID."""
    created = client.post(
        "/orders",
        json={"customer_name": "David", "item_name": "USB Hub", "quantity": 1},
    ).json()

    order_id = created["id"]
    response = client.get(f"/orders/{order_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order_id
    assert data["customer_name"] == "David"
    assert data["item_name"] == "USB Hub"


def test_get_order_by_id_not_found(client: TestClient) -> None:
    """Test retrieving nonexistent order ID returns 404."""
    response = client.get("/orders/999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_order_invalid_id(client: TestClient) -> None:
    """Test non-positive ID returns 422 validation error."""
    response = client.get("/orders/0")
    assert response.status_code == 422


def test_database_failure_handling(client: TestClient) -> None:
    """Test graceful handling of database failure without leaking sensitive info."""
    with patch(
        "app.db.get_db_connection",
        side_effect=psycopg.OperationalError("password=secret connection dropped"),
    ):
        response = client.post(
            "/orders",
            json={"customer_name": "Eve", "item_name": "Webcam", "quantity": 1},
        )
        assert response.status_code == 503
        data = response.json()
        assert "secret" not in response.text
        assert "Database service unavailable" in data["detail"]


def test_data_persistence(client: TestClient) -> None:
    """Test persistence: orders survive across independent API calls."""
    post_res = client.post(
        "/orders",
        json={"customer_name": "Frank", "item_name": "Headphones", "quantity": 1},
    )
    assert post_res.status_code == 201
    order_id = post_res.json()["id"]

    # Retrieve again in an independent request
    get_res = client.get(f"/orders/{order_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == order_id
    assert get_res.json()["customer_name"] == "Frank"


def test_list_orders_database_failure(client: TestClient) -> None:
    """Test list_orders graceful 503 on database operational error."""
    with patch(
        "app.db.get_db_connection",
        side_effect=psycopg.OperationalError("database offline"),
    ):
        response = client.get("/orders")
        assert response.status_code == 503
        assert response.json()["detail"] == "Database service unavailable."


def test_get_order_database_failure(client: TestClient) -> None:
    """Test get_order graceful 503 on database operational error."""
    with patch(
        "app.db.get_db_connection",
        side_effect=psycopg.OperationalError("database offline"),
    ):
        response = client.get("/orders/1")
        assert response.status_code == 503
        assert response.json()["detail"] == "Database service unavailable."


def test_db_pool_none_health() -> None:
    """Test check_db_health returns False when pool is uninitialized."""
    from app import db

    with patch.object(db, "pool", None):
        assert db.check_db_health() is False
