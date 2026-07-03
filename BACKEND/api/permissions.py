from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import User, UserRole, RolePermission


def get_user_roles(user: User) -> list[str]:
    return [user_role.role.name for user_role in user.roles]


def get_user_permissions(db: Session, user: User) -> list[str]:
    role_ids = [user_role.role_id for user_role in user.roles]

    if not role_ids:
        return []

    rows = db.query(RolePermission).filter(
        RolePermission.role_id.in_(role_ids)
    ).all()

    return [row.permission.code for row in rows]


def require_roles(allowed_roles: list[str]):
    def checker(current_user: User = Depends(get_current_user)):
        roles = get_user_roles(current_user)

        if not any(role in allowed_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )

        return current_user

    return checker


def require_permissions(required_permissions: list[str]):
    def checker(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        roles = get_user_roles(current_user)

        if "super_admin" in roles:
            return current_user

        permissions = get_user_permissions(db, current_user)

        if not any(permission in permissions for permission in required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied"
            )

        return current_user

    return checker