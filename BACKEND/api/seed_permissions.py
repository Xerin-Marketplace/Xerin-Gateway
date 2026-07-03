from api.database import SessionLocal
from api.models import Role, Permission, RolePermission
from api.enums import PermissionCode
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import SessionLocal
from api.models import Role, Permission, RolePermission
from api.enums import PermissionCode

db = SessionLocal()


DEFAULT_ROLE_PERMISSIONS = {
    "customer": [
        PermissionCode.view_profile.value,
        PermissionCode.update_profile.value,
        PermissionCode.manage_addresses.value,
        PermissionCode.can_view_products.value,
    ],
    "seller": [
        PermissionCode.view_profile.value,
        PermissionCode.update_profile.value,
        PermissionCode.manage_addresses.value,
        PermissionCode.view_seller_profile.value,
        PermissionCode.update_seller_profile.value,
        PermissionCode.upload_kyc.value,
        PermissionCode.manage_payout_accounts.value,
        PermissionCode.manage_products.value,
        PermissionCode.can_view_products.value,
    ],
    "admin": [
        PermissionCode.view_profile.value,
        PermissionCode.update_profile.value,
        PermissionCode.manage_users.value,
        PermissionCode.can_view_business_categories.value,
        PermissionCode.can_view_product_categories.value,
        PermissionCode.can_view_brands.value,
        PermissionCode.can_view_sellers.value,
        PermissionCode.can_approve_sellers.value,
        PermissionCode.can_reject_sellers.value,
        PermissionCode.can_view_products.value,
    ],
    "super_admin": [p.value for p in PermissionCode],
}


for permission_code in PermissionCode:
    permission = db.query(Permission).filter(
        Permission.code == permission_code.value
    ).first()

    if not permission:
        permission = Permission(
            code=permission_code.value,
            name=permission_code.value.replace("_", " ").title(),
            description=f"Allows user to {permission_code.value.replace('_', ' ')}",
        )
        db.add(permission)

db.commit()

for role_name, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
    role = db.query(Role).filter(Role.name == role_name).first()

    if not role:
        role = Role(name=role_name, description=f"{role_name} role")
        db.add(role)
        db.commit()
        db.refresh(role)

    for permission_code in permission_codes:
        permission = db.query(Permission).filter(
            Permission.code == permission_code
        ).first()

        exists = db.query(RolePermission).filter(
            RolePermission.role_id == role.id,
            RolePermission.permission_id == permission.id,
        ).first()

        if not exists:
            db.add(RolePermission(role_id=role.id, permission_id=permission.id))

db.commit()
db.close()

print("Permissions seeded successfully")