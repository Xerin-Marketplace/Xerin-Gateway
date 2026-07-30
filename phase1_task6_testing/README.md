# Xerin Marketplace — Phase One Task 6

This package adds automated regression tests matched to the uploaded post-Task-5B `api/` folder.

## 1. Install

From the backend root:

```bash
cp -r phase1_task6_testing/tests .
cp phase1_task6_testing/pytest.ini .
cp phase1_task6_testing/requirements-test.txt .
cp phase1_task6_testing/.env.test.example .

pip install -r requirements-test.txt
```

## 2. Run tests that do not need a database

```bash
pytest -m "not integration" -v
```

These cover:

- application startup and liveness
- OpenAPI generation
- duplicate route detection
- schema validation
- JWT, OTP, and refresh-token hashing
- webhook-secret rejection
- model security constraints

## 3. Important expected first failure

The current uploaded code contains duplicate `GET /api/v1/admin/permissions` routes. Therefore:

```bash
pytest tests/test_route_contracts.py -v
```

should identify that duplicate until one of the two handlers is removed from `api/routers/admin.py`.

The current `api/schemas.py` also defines `RoleResponse` twice. Keep the later Pydantic V2 version and remove the earlier legacy version.

See `CURRENT_CODE_FINDINGS.md`.

## 4. Create a dedicated PostgreSQL test database

Never point tests at the production database.

Example:

```bash
sudo -u postgres psql <<'SQL'
CREATE USER xerin_test WITH PASSWORD 'xerin_test_password';
CREATE DATABASE xerin_test OWNER xerin_test;
GRANT ALL PRIVILEGES ON DATABASE xerin_test TO xerin_test;
SQL
```

Copy the environment template:

```bash
cp .env.test.example .env.test
```

Edit `.env.test`, then export it:

```bash
set -a
source .env.test
set +a
```

Confirm the database name before running tests:

```bash
python - <<'PY'
import os
from sqlalchemy.engine import make_url
url = make_url(os.environ["TEST_DATABASE_URL"])
print("Test database:", url.database)
assert "test" in (url.database or "").lower(), "Refusing a database without 'test' in its name"
PY
```

## 5. Run the full suite

```bash
pytest -v
```

With coverage:

```bash
pytest --cov=api --cov-report=term-missing --cov-report=html
```

Open `htmlcov/index.html` locally to inspect coverage.

## 6. Test isolation

The PostgreSQL integration fixture creates the schema at the beginning of the test session and drops it at the end. Each test also runs inside a transaction that is rolled back.

Use only a dedicated disposable test database.

## 7. No Alembic migration

Task 6 adds tests only. It does not change database tables and does not require a migration.
