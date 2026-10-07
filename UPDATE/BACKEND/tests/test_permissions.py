import pytest
from fastapi import HTTPException

from api.models import Permission, Role, RolePermission, User, UserPermission, UserRole, UserStatus
from api.permissions import _authorize, get_user_permissions
from api.security import hash_password

pytestmark = pytest.mark.integration


def _user(db, email: str):
    user = User(
        first_name="Test",
        last_name="User",
        email=email,
        phone="+255700000099",
        password_hash=hash_password("StrongPassword123"),
        status=UserStatus.active,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def test_role_and_direct_permissions_are_combined(db):
    user = _user(db, "permissions@example.com")
    role = Role(name="test-role")
    role_permission = Permission(code="products:read", name="Read products")
    direct_permission = Permission(code="products:write", name="Write products")
    db.add_all([role, role_permission, direct_permission])
    db.flush()
    db.add_all([
        UserRole(user_id=user.id, role_id=role.id),
        RolePermission(role_id=role.id, permission_id=role_permission.id),
        UserPermission(user_id=user.id, permission_id=direct_permission.id),
    ])
    db.flush()

    assert get_user_permissions(db, user) == {"products:read", "products:write"}


def test_authorize_rejects_missing_permission(db):
    user = _user(db, "denied@example.com")
    with pytest.raises(HTTPException) as exc:
        _authorize(db=db, current_user=user, permission_codes=["admin:danger"], require_all=True)
    assert exc.value.status_code == 403
