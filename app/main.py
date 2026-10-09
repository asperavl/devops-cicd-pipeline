import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated

import psycopg
from fastapi import FastAPI, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import db

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    try:
        db.init_db()
    except Exception as exc:
        logger.warning("Could not initialize database on startup: %s", exc)
    yield
    db.close_db()


app = FastAPI(
    title="Order Management API",
    version="1.0.0",
    lifespan=lifespan,
)


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=255)
    item_name: str = Field(..., min_length=1, max_length=255)
    quantity: int = Field(..., gt=0, description="Quantity must be a positive integer")


class OrderResponse(BaseModel):
    id: int
    customer_name: str
    item_name: str
    quantity: int
    created_at: datetime


@app.get("/", status_code=status.HTTP_200_OK)
def read_root() -> dict[str, str]:
    """Return basic application information."""
    return {
        "service": "Order Management API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
def health_check() -> JSONResponse:
    """Return health status, distinguishing app from database connectivity."""
    db_healthy = db.check_db_health()
    content = {
        "status": "healthy" if db_healthy else "degraded",
        "database": "connected" if db_healthy else "disconnected",
    }
    status_code = (
        status.HTTP_200_OK if db_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    return JSONResponse(status_code=status_code, content=content)


@app.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate) -> dict[str, object]:
    """Create a new order using parameterized SQL query."""
    insert_sql = """
    INSERT INTO orders (customer_name, item_name, quantity)
    VALUES (%s, %s, %s)
    RETURNING id, customer_name, item_name, quantity, created_at;
    """
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    insert_sql,
                    (payload.customer_name, payload.item_name, payload.quantity),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to record order.",
                )
            return dict(row)
    except HTTPException:
        raise
    except (psycopg.OperationalError, RuntimeError) as exc:
        logger.error("Database unavailable while creating order: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from None
    except Exception as exc:
        logger.error("Internal database error while creating order: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed.",
        ) from None


@app.get("/orders", response_model=list[OrderResponse], status_code=status.HTTP_200_OK)
def list_orders() -> list[dict[str, object]]:
    """Retrieve all orders ordered by creation timestamp."""
    select_sql = """
    SELECT id, customer_name, item_name, quantity, created_at
    FROM orders
    ORDER BY created_at DESC;
    """
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(select_sql)
                rows = cur.fetchall()
            return [dict(row) for row in rows]
    except (psycopg.OperationalError, RuntimeError) as exc:
        logger.error("Database unavailable while listing orders: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from None
    except Exception as exc:
        logger.error("Database query error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed.",
        ) from None


@app.get("/orders/{id}", response_model=OrderResponse, status_code=status.HTTP_200_OK)
def get_order(id: Annotated[int, Path(gt=0)]) -> dict[str, object]:
    """Retrieve a single order by ID or return 404."""
    select_sql = """
    SELECT id, customer_name, item_name, quantity, created_at
    FROM orders
    WHERE id = %s;
    """
    try:
        with db.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(select_sql, (id,))
                row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order with ID {id} not found.",
                )
            return dict(row)
    except HTTPException:
        raise
    except (psycopg.OperationalError, RuntimeError) as exc:
        logger.error("Database unavailable while fetching order: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable.",
        ) from None
    except Exception as exc:
        logger.error("Database query error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database operation failed.",
        ) from None
