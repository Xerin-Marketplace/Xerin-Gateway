from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.enums import PermissionCode
from api.models import Permission, Role, RolePermission

logger = logging.getLogger(__name__)


DEFAULT_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "customer": {
        PermissionCode.view_profile.value,
        PermissionCode.update_profile.value,
        PermissionCode.manage_addresses.value,
        PermissionCode.refunds_create.value,
        PermissionCode.can_view_products.value,
        PermissionCode.can_view_public_stores.value,
        PermissionCode.shipping_track.value,
    },
    "seller": {
        PermissionCode.view_profile.value,
        PermissionCode.update_profile.value,
        PermissionCode.manage_addresses.value,
        PermissionCode.refunds_create.value,
        PermissionCode.view_seller_profile.value,
        PermissionCode.update_seller_profile.value,
        PermissionCode.upload_kyc.value,
        PermissionCode.manage_payout_accounts.value,
        PermissionCode.manage_products.value,
        PermissionCode.seller_products_create.value,
        PermissionCode.seller_products_read.value,
        PermissionCode.seller_products_update.value,
        PermissionCode.seller_products_delete.value,
        PermissionCode.seller_product_images_manage.value,
        PermissionCode.seller_products_submit.value,
        PermissionCode.seller_product_variants_manage.value,
        PermissionCode.seller_orders_read.value,
        PermissionCode.seller_orders_manage.value,
        PermissionCode.seller_inventory_read.value,
        PermissionCode.seller_inventory_manage.value,
        PermissionCode.seller_delivery_read.value,
        PermissionCode.seller_delivery_request.value,
        PermissionCode.seller_store_read.value,
        PermissionCode.seller_store_update.value,
        PermissionCode.seller_store_branding.value,
        PermissionCode.can_view_products.value,
        PermissionCode.can_view_public_stores.value,
        PermissionCode.shipping_track.value,
        PermissionCode.shipping_manage_own.value,
        PermissionCode.seller_earnings_read.value,
        PermissionCode.wallet_read.value,
        PermissionCode.wallet_payout.value,
        PermissionCode.refunds_create.value,
        PermissionCode.analytics_seller_read.value,
        # Legacy permissions currently used by store profile/media routes.
        PermissionCode.view_own_store.value,
        PermissionCode.update_own_store.value,
        PermissionCode.upload_store_logo.value,
        PermissionCode.upload_store_banner.value,
        # Granular permissions used by gallery and opening-hours routes.
        PermissionCode.STORE_VIEW_OWN.value,
        PermissionCode.STORE_UPDATE_OWN.value,
        PermissionCode.STORE_UPLOAD_MEDIA.value,
        PermissionCode.STORE_MANAGE_GALLERY.value,
        PermissionCode.STORE_MANAGE_HOURS.value,
    },
    "admin": {
        PermissionCode.view_profile.value,
        PermissionCode.update_profile.value,
        PermissionCode.manage_users.value,
        PermissionCode.can_view_users.value,
        PermissionCode.can_view_business_categories.value,
        PermissionCode.can_view_product_categories.value,
        PermissionCode.can_view_brands.value,
        PermissionCode.can_view_sellers.value,
        PermissionCode.can_view_pending_sellers.value,
        PermissionCode.can_view_seller_documents.value,
        PermissionCode.can_approve_sellers.value,
        PermissionCode.can_reject_sellers.value,
        PermissionCode.can_view_products.value,
        PermissionCode.can_approve_products.value,
        PermissionCode.can_reject_products.value,
        PermissionCode.orders_read.value,
        PermissionCode.payments_read.value,
        PermissionCode.coupons_read.value,
        PermissionCode.shipping_read.value,
        PermissionCode.shipping_write.value,
        PermissionCode.shipping_track.value,
        PermissionCode.shipping_manage_all.value,
        PermissionCode.commissions_read.value,
        PermissionCode.commissions_write.value,
        PermissionCode.commissions_manage.value,
        PermissionCode.wallet_read.value,
        PermissionCode.wallet_manage.value,
        PermissionCode.wallet_adjust.value,
        PermissionCode.refunds_read.value,
        PermissionCode.refunds_review.value,
        PermissionCode.refunds_process.value,
        PermissionCode.analytics_admin_read.value,
        PermissionCode.audit_logs_read.value,
        PermissionCode.security_events_read.value,
        PermissionCode.STORE_ADMIN_VIEW.value,
    },
    "super_admin": {permission.value for permission in PermissionCode},
}


def _permission_name(code: str) -> str:
    return code.replace(":", " ").replace("_", " ").title()


def seed_permissions(db: Session) -> None:
    try:
        permission_by_code: dict[str, Permission] = {}

        for permission_code in PermissionCode:
            code = permission_code.value
            permission = (
                db.query(Permission)
                .filter(Permission.code == code)
                .first()
            )
            if permission is None:
                permission = Permission(
                    code=code,
                    name=_permission_name(code),
                    description=f"Allows the assigned role or user to {_permission_name(code).lower()}.",
                )
                db.add(permission)
                db.flush()
            permission_by_code[code] = permission

        for role_name, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if role is None:
                role = Role(
                    name=role_name,
                    description=f"Default {role_name.replace('_', ' ')} role",
                )
                db.add(role)
                db.flush()

            existing_codes = {
                row.permission.code
                for row in db.query(RolePermission)
                .filter(RolePermission.role_id == role.id)
                .all()
                if row.permission is not None
            }

            for code in permission_codes - existing_codes:
                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission_by_code[code].id,
                    )
                )

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Permission seeding failed")
        raise


def main() -> None:
    db = SessionLocal()
    try:
        seed_permissions(db)

        print("Permissions and default roles seeded successfully")
    finally:
        db.close()


if __name__ == "__main__":
    main()
