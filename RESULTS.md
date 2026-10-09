# CI/CD Pipeline & Delivery Evidence (RESULTS.md)

This document provides empirical evidence and operational results for the containerized Order Management API and its automated delivery pipeline.

---

## 1. Automated Test Suite & Coverage

The automated test suite runs against a live PostgreSQL 16 instance, validating HTTP contracts, database persistence, transaction rollbacks, input validation, and connection error handling.

- **Test Framework**: `pytest` 9.1.1, `pytest-cov` 7.1.0, `httpx` / `TestClient`
- **Total Tests Executed**: 15
- **Passed**: 15
- **Failed**: 0
- **Execution Time**: ~2.3 seconds
- **Enforced Coverage Gate**: Minimum 80% (`--cov-fail-under=80`)
- **Actual Code Coverage**: **81.93%**

### Coverage Breakdown by Module

| Module | Statements | Missing | Coverage | Status |
| :--- | :--- | :--- | :--- | :--- |
| `app/__init__.py` | 0 | 0 | 100% | PASS |
| `app/config.py` | 16 | 0 | 100% | PASS |
| `app/db.py` | 57 | 17 | 70.18% | PASS |
| `app/main.py` | 93 | 13 | 86.02% | PASS |
| **TOTAL** | **166** | **30** | **81.93%** | **PASS** |

### Test Cases Summary
1. `test_read_root`: Validates `GET /` service metadata and status.
2. `test_health_healthy`: Validates `GET /health` returns 200 and `"database": "connected"`.
3. `test_health_unhealthy`: Validates `GET /health` returns 503 and `"database": "disconnected"` when DB is unreachable.
4. `test_create_order_success`: Validates `POST /orders` inserts order, returns 201 with generated `id` and timestamp.
5. `test_create_order_missing_fields`: Validates 422 Unprocessable Entity when required fields are missing.
6. `test_create_order_invalid_quantity`: Validates 422 rejection when quantity is zero or negative.
7. `test_list_orders`: Validates `GET /orders` returns array of orders sorted chronologically.
8. `test_get_order_by_id_success`: Validates `GET /orders/{id}` retrieves existing order.
9. `test_get_order_by_id_not_found`: Validates `GET /orders/{id}` returns 404 for nonexistent order ID.
10. `test_get_order_invalid_id`: Validates path validation rejects non-positive IDs with 422.
11. `test_database_failure_handling`: Validates database error during order creation safely returns 503 without leaking credentials.
12. `test_data_persistence`: Validates database records persist across distinct request cycles.
13. `test_list_orders_database_failure`: Validates 503 response when database fails during listing.
14. `test_get_order_database_failure`: Validates 503 response when database fails during single order lookup.
15. `test_db_pool_none_health`: Validates `check_db_health` cleanly returns `False` when pool is uninitialized.

---

## 2. Code Quality & Linting

- **Linter & Formatter**: `Ruff` 0.17.0
- **Rules**: Pyflakes (`F`), pycodestyle error (`E`), isort (`I`)
- **Status**: 100% compliant (`All checks passed!`)

---

## 3. Container Build & Security Scan

### Dockerfile Design
- **Base Image**: `python:3.12-slim`
- **Builder**: Astral `uv` binary copied directly from official image `ghcr.io/astral-sh/uv`
- **Security**:
  - Runs under dedicated unprivileged non-root user (`appuser`).
  - `.dockerignore` excludes git history, virtual environments, `.env` files, tests, and caches.
  - Signal handling: Directly executes `uvicorn` with graceful shutdown handling.

### Trivy Container Vulnerability Scan
- **Scanner**: `aquasecurity/trivy-action`
- **Policy**:
  - Scans for `CRITICAL` and `HIGH` severity vulnerabilities.
  - Enforces `exit-code: 1` on unhandled high/critical issues.
  - Ignores unfixed CVEs (`ignore-unfixed: true`) to avoid blocking pipelines on upstream zero-days without available vendor patches.

---

## 4. GitHub Actions CI/CD Pipeline Summary

Workflows are codified in `.github/workflows/ci.yml`:

| Stage | Trigger | Actions / Checks | Status / Gate |
| :--- | :--- | :--- | :--- |
| **Stage 1 & 2: Test & Quality** | Pull Request & Push | Ruff lint/format, Postgres 16 service, pytest suite | Fail if tests fail or coverage < 80% |
| **Stage 3: Docker Build** | On Test Pass | Docker Buildx with GitHub Actions cache | Verifies clean image build |
| **Stage 4: Security Scan** | On Build | Trivy vulnerability scan | Fails on HIGH/CRITICAL vulnerabilities |
| **Stage 5: Smoke Test** | On Scan Pass | Spawns test container and runs health check curl | Verifies running artifact |
| **Stage 6: Registry Publish** | Push to `main` | Push immutable `sha-<commit>` and `latest` tags to GHCR | GITHUB_TOKEN authentication with `packages: write` |

---

## 5. End-to-End Smoke Test Verification

Running the API with Docker Compose:

```bash
$ curl -s http://localhost:8000/health
{"status":"healthy","database":"connected"}

$ curl -s -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"customer_name": "Test User", "item_name": "Mechanical Keyboard", "quantity": 1}'
{"id":1,"customer_name":"Test User","item_name":"Mechanical Keyboard","quantity":1,"created_at":"2026-10-10T03:52:00+00:00"}

$ curl -s http://localhost:8000/orders/1
{"id":1,"customer_name":"Test User","item_name":"Mechanical Keyboard","quantity":1,"created_at":"2026-10-10T03:52:00+00:00"}
```

---

## 6. Operational Notes & Limitations

1. **Host vs Container Port Mapping**: The API container communicates via Docker's bridge network (`db:5432`). Host development tools or pytest connect using the host port mapping (`${DB_PORT:-5432}`).
2. **Schema Management**: Relies on idempotent `CREATE TABLE IF NOT EXISTS` at application startup. For high-velocity team environments with complex relational schema migrations, Alembic would be the natural progression.

