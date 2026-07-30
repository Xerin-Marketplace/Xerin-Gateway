from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest

# Settings are instantiated while importing api.config, so safe test defaults must
# exist before importing any application module.
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", os.getenv("TEST_DATABASE_URL", "postgresql://invalid:invalid@127.0.0.1:1/invalid"))
os.environ.setdefault("SECRET_KEY", "test-secret-key-that-is-longer-than-32-characters")
os.environ.setdefault("ACCESS_TOKEN_SECRET", "test-access-secret-that-is-longer-than-32-characters")
os.environ.setdefault("REFRESH_TOKEN_SECRET", "test-refresh-secret-that-is-longer-than-32-characters")
os.environ.setdefault("TRUSTED_HOSTS", "testserver,localhost,127.0.0.1")
os.environ.setdefault("SERVE_LOCAL_UPLOADS", "false")
os.environ.setdefault("PAYMENT_WEBHOOK_SECRET", "test-webhook-secret-change-me")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database import Base
from api.deps import get_db
from api.main import api
from api.models import Permission, Role, RolePermission


@pytest.fixture(scope="session")
def client() -> Generator[TestClient, None, None]:
    with TestClient(api) as test_client:
        yield test_client


def _test_database_url() -> str | None:
    return os.getenv("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def integration_engine():
    url = _test_database_url()
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    if "postgresql" not in url:
        pytest.skip("Integration suite requires PostgreSQL because models use JSONB and PostgreSQL UUID")

    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db(integration_engine) -> Generator[Session, None, None]:
    connection = integration_engine.connect()
    transaction = connection.begin()
    TestingSession = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    session = TestingSession()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    api.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        api.dependency_overrides.pop(get_db, None)
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def db_client(db: Session) -> Generator[TestClient, None, None]:
    with TestClient(api) as test_client:
        yield test_client


@pytest.fixture()
def seeded_security(db: Session) -> dict[str, object]:
    role_names = ("customer", "seller", "admin", "super_admin")
    roles = {}
    for name in role_names:
        role = Role(name=name, description=f"Test {name}")
        db.add(role)
        db.flush()
        roles[name] = role

    permission_codes = (
        "can_create_product_categories",
        "can_create_brands",
        "payments:read",
        "orders:read",
        "orders:write",
        "coupons:read",
        "coupons:write",
    )
    permissions = {}
    for code in permission_codes:
        permission = Permission(code=code, name=code, description="Test permission")
        db.add(permission)
        db.flush()
        permissions[code] = permission

    for permission in permissions.values():
        db.add(RolePermission(role_id=roles["admin"].id, permission_id=permission.id))
        db.add(RolePermission(role_id=roles["super_admin"].id, permission_id=permission.id))

    db.flush()
    return {"roles": roles, "permissions": permissions}
