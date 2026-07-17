import enum

class StoreStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    active = "active"
    rejected = "rejected"
    suspended = "suspended"
    closed = "closed"
    
class DayOfWeek(str, enum.Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"    

class PermissionCode(str, enum.Enum):
    view_all_users = "view_all_users"
    can_create_users = "can_create_users"
    can_view_users = "can_view_users"
    can_update_users = "can_update_users"
    can_delete_users = "can_delete_users"
    can_create_admin_users = "can_create_admin_users"
    view_profile = "view_profile"
    update_profile = "update_profile"
    manage_users = "manage_users"
    manage_addresses = "manage_addresses"
    view_seller_profile = "view_seller_profile"
    update_seller_profile = "update_seller_profile"
    upload_kyc = "upload_kyc"
    manage_payout_accounts = "manage_payout_accounts"
    manage_products = "manage_products"
    can_assign_permissions = "can_assign_permissions"

    can_create_business_categories = "can_create_business_categories"
    can_view_business_categories = "can_view_business_categories"
    can_update_business_categories = "can_update_business_categories"
    can_delete_business_categories = "can_delete_business_categories"

    can_create_product_categories = "can_create_product_categories"
    can_view_product_categories = "can_view_product_categories"
    can_delete_product_categories = "can_delete_product_categories"

    can_create_brands = "can_create_brands"
    can_view_brands = "can_view_brands"
    can_delete_brands = "can_delete_brands"

    can_view_sellers = "can_view_sellers"
    can_view_pending_sellers = "can_view_pending_sellers"
    can_view_seller_documents = "can_view_seller_documents"
    can_approve_sellers = "can_approve_sellers"
    can_reject_sellers = "can_reject_sellers"

    can_view_products = "can_view_products"
    can_approve_products = "can_approve_products"
    can_reject_products = "can_reject_products"

    orders_read = "orders:read"
    payments_read = "payments:read"
    inventory_manage = "inventory:manage"
    coupons_write = "coupons:write"
    coupons_read = "coupons:read"
    
    view_own_store = "view_own_store"
    update_own_store = "update_own_store"
    upload_store_logo = "upload_store_logo"
    upload_store_banner = "upload_store_banner"
    can_view_public_stores = "can_view_public_stores"
    manage_all_stores = "manage_all_stores"
    
    STORE_VIEW_OWN = "store:view_own"
    STORE_UPDATE_OWN = "store:update_own"
    STORE_UPLOAD_MEDIA = "store:upload_media"
    STORE_MANAGE_GALLERY = "store:manage_gallery"
    STORE_MANAGE_HOURS = "store:manage_hours"

    STORE_ADMIN_VIEW = "store:admin_view"
    STORE_ADMIN_UPDATE = "store:admin_update"
    STORE_ADMIN_VERIFY = "store:admin_verify"
    STORE_ADMIN_FEATURE = "store:admin_feature"
    STORE_ADMIN_DELETE = "store:admin_delete"
    
