import pytest

from api.models import Role, User, UserRole, UserStatus
from api.routers import auth
from api.security import hash_password

pytestmark = pytest.mark.integration


def test_register_assigns_customer_role(db_client, db, monkeypatch):
    db.add(Role(name="customer", description="Customer"))
    db.flush()
    monkeypatch.setattr(auth, "generate_otp", lambda: "123456")
    monkeypatch.setattr(auth, "send_email", lambda **_: None)
    monkeypatch.setattr(auth, "send_sms", lambda **_: None)

    response = db_client.post(
        "/api/v1/auth/register",
        json={
            "first_name": "Adam",
            "last_name": "Tester",
            "email": "new@example.com",
            "phone": "+255700000010",
            "password": "StrongPassword123",
        },
    )
    assert response.status_code == 200, response.text

    user = db.query(User).filter(User.email == "new@example.com").one()
    assigned = db.query(UserRole).filter(UserRole.user_id == user.id).one()
    assert assigned.role.name == "customer"
    assert user.status == UserStatus.pending_verification
    assert user.is_verified is False


def test_verified_user_can_login(db_client, db):
    user = User(
        first_name="Login",
        last_name="User",
        email="login@example.com",
        phone="+255700000011",
        password_hash=hash_password("StrongPassword123"),
        status=UserStatus.active,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    response = db_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "StrongPassword123"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_unverified_user_cannot_login(db_client, db):
    db.add(User(
        first_name="Pending",
        last_name="User",
        email="pending@example.com",
        phone="+255700000012",
        password_hash=hash_password("StrongPassword123"),
        status=UserStatus.pending_verification,
        is_verified=False,
    ))
    db.flush()

    response = db_client.post(
        "/api/v1/auth/login",
        json={"email": "pending@example.com", "password": "StrongPassword123"},
    )
    assert response.status_code == 403
