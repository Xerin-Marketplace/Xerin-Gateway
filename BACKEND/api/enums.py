import enum


class PermissionCode(str, enum.Enum):
    view_profile = "view_profile"
    update_profile = "update_profile"

    manage_addresses = "manage_addresses"

    view_seller_profile = "view_seller_profile"
    update_seller_profile = "update_seller_profile"
    upload_kyc = "upload_kyc"
    manage_payout_accounts = "manage_payout_accounts"

    manage_products = "manage_products"
    view_products = "view_products"

    manage_users = "manage_users"
    manage_admins = "manage_admins"

    manage_business_categories = "manage_business_categories"
    manage_product_categories = "manage_product_categories"
    manage_brands = "manage_brands"

    approve_sellers = "approve_sellers"
    reject_sellers = "reject_sellers"
    view_sellers = "view_sellers"

    approve_products = "approve_products"
    reject_products = "reject_products"

    manage_orders = "manage_orders"
    view_reports = "view_reports"