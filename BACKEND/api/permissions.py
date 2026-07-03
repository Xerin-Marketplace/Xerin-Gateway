from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import User, RolePermission, UserPermission

def get_user_permissions(db: Session, user: User) -> list[str]:
    role_ids = [user_role.role_id for user_role in user.roles]

    permissions = set()

    if role_ids:
        role_permissions = db.query(RolePermission).filter(
            RolePermission.role_id.in_(role_ids)
        ).all()

        for row in role_permissions:
            permissions.add(row.permission.code)

    user_permissions = db.query(UserPermission).filter(
        UserPermission.user_id == user.id
    ).all()

    for row in user_permissions:
        permissions.add(row.permission.code)

    return list(permissions)


def require_permission(permission_code: str):
    def checker(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ):
        roles = [user_role.role.name for user_role in current_user.roles]

        if "super_admin" in roles:
            return current_user

        permissions = get_user_permissions(db, current_user)

        if permission_code not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_code}"
            )

        return current_user

    return checker