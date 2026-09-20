from collections.abc import Iterable

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import RolePermission, User, UserPermission

SUPER_ADMIN_ROLE = "super_admin"


def get_user_role_names(user: User) -> set[str]:
    return {
        user_role.role.name
        for user_role in user.roles
        if user_role.role is not None
    }


def get_user_permissions(db: Session, user: User) -> set[str]:
    role_ids = [user_role.role_id for user_role in user.roles]
    permissions: set[str] = set()

    if role_ids:
        rows = (
            db.query(RolePermission)
            .filter(RolePermission.role_id.in_(role_ids))
            .all()
        )
        permissions.update(
            row.permission.code
            for row in rows
            if row.permission is not None
        )

    direct_rows = (
        db.query(UserPermission)
        .filter(UserPermission.user_id == user.id)
        .all()
    )
    permissions.update(
        row.permission.code
        for row in direct_rows
        if row.permission is not None
    )

    return permissions


def _authorize(
    *,
    db: Session,
    current_user: User,
    permission_codes: Iterable[str],
    require_all: bool,
) -> User:
    roles = get_user_role_names(current_user)
    if SUPER_ADMIN_ROLE in roles:
        return current_user

    required = set(permission_codes)
    granted = get_user_permissions(db, current_user)

    allowed = required.issubset(granted) if require_all else bool(required & granted)
    if not allowed:
        detail = ", ".join(sorted(required))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied. Required: {detail}",
        )

    return current_user


def require_permission(permission_code: str):
    def checker(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        return _authorize(
            db=db,
            current_user=current_user,
            permission_codes=[permission_code],
            require_all=True,
        )

    return checker


def require_all_permissions(*permission_codes: str):
    def checker(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        return _authorize(
            db=db,
            current_user=current_user,
            permission_codes=permission_codes,
            require_all=True,
        )

    return checker


def require_any_permission(*permission_codes: str):
    def checker(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        return _authorize(
            db=db,
            current_user=current_user,
            permission_codes=permission_codes,
            require_all=False,
        )

    return checker
