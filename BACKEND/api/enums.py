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
    # Users and profiles
    view_all_users = "view_all_users"
    can_create_users = "can_create_users"
    can_view_users = "can_view_users"
    can_update_users = "can_update_users"
    can_delete_users = "can_delete_users"
    can_create_admin_users = "can_create_admin_users"
    can_assign_permissions = "can_assign_permissions"
    view_profile = "view_profile"
    update_profile = "update_profile"
    manage_users = "manage_users"
    manage_addresses = "manage_addresses"

    # Sellers
    view_seller_profile = "view_seller_profile"
    update_seller_profile = "update_seller_profile"
    upload_kyc = "upload_kyc"
    manage_payout_accounts = "manage_payout_accounts"
    can_view_sellers = "can_view_sellers"
    can_view_pending_sellers = "can_view_pending_sellers"
    can_view_seller_documents = "can_view_seller_documents"
    can_approve_sellers = "can_approve_sellers"
    can_reject_sellers = "can_reject_sellers"

    # Business and product catalogue
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

    manage_products = "manage_products"
    can_view_products = "can_view_products"
    can_approve_products = "can_approve_products"
    can_reject_products = "can_reject_products"
    seller_products_create = "seller_products:create"
    seller_products_read = "seller_products:read"
    seller_products_update = "seller_products:update"
    seller_products_delete = "seller_products:delete"
    seller_product_images_manage = "seller_product_images:manage"
    seller_products_submit = "seller_products:submit"
    seller_product_variants_manage = "seller_product_variants:manage"
    seller_orders_read = "seller_orders:read"
    seller_orders_manage = "seller_orders:manage"
    seller_inventory_read = "seller_inventory:read"
    seller_inventory_manage = "seller_inventory:manage"
    seller_delivery_read = "seller_delivery:read"
    seller_delivery_request = "seller_delivery:request"
    seller_store_read = "seller_store:read"
    seller_store_update = "seller_store:update"
    seller_store_branding = "seller_store:branding"
    reviews_create = "reviews:create"
    reviews_read = "reviews:read"
    reviews_update = "reviews:update"
    reviews_delete = "reviews:delete"
    seller_reviews_read = "seller_reviews:read"
    seller_reviews_reply = "seller_reviews:reply"
    seller_reviews_report = "seller_reviews:report"
    admin_reviews_read = "admin_reviews:read"
    admin_reviews_moderate = "admin_reviews:moderate"

    # Support tickets / customer care.
    # Permission-based by design: any custom role can receive these.
    support_tickets_create = "support_tickets:create"
    support_tickets_read_own = "support_tickets:read_own"
    support_tickets_reply_own = "support_tickets:reply_own"
    support_tickets_read = "support_tickets:read"
    support_tickets_manage = "support_tickets:manage"
    support_tickets_reply = "support_tickets:reply"
    support_tickets_assign = "support_tickets:assign"
    support_tickets_resolve = "support_tickets:resolve"
    wishlist_read = "wishlist:read"
    wishlist_manage = "wishlist:manage"
    promotions_read = "promotions:read"
    promotions_create = "promotions:create"
    promotions_update = "promotions:update"
    promotions_delete = "promotions:delete"
    campaigns_manage = "campaigns:manage"

    notifications_read = "notifications:read"
    notifications_manage = "notifications:manage"
    admin_notifications_read = "admin_notifications:read"
    admin_notifications_manage = "admin_notifications:manage"
    admin_notification_templates_manage = "admin_notification_templates:manage"

    product_questions_read = "product_questions:read"
    product_questions_create = "product_questions:create"
    product_questions_update = "product_questions:update"
    product_questions_delete = "product_questions:delete"
    product_answers_create = "product_answers:create"
    product_answers_update = "product_answers:update"
    seller_questions_read = "seller_questions:read"
    seller_questions_answer = "seller_questions:answer"
    product_questions_moderate = "product_questions:moderate"

    search_read = "search:read"
    recommendations_read = "recommendations:read"
    search_history_manage = "search_history:manage"
    seller_search_analytics_read = "seller_search_analytics:read"

    admin_dashboard_read = "admin_dashboard:read"
    admin_dashboard_finance_read = "admin_dashboard_finance:read"
    admin_dashboard_operations_read = "admin_dashboard_operations:read"
    admin_dashboard_security_read = "admin_dashboard_security:read"
    admin_system_alerts_manage = "admin_system_alerts:manage"
    admin_activity_logs_read = "admin_activity_logs:read"

    # Commerce
    orders_read = "orders:read"
    payments_read = "payments:read"
    payments_dashboard = "payments:dashboard"
    payment_methods_read = "payment_methods:read"
    payment_providers_read = "payment_providers:read"
    payment_providers_manage = "payment_providers:manage"
    payment_disputes_read = "payment_disputes:read"
    payment_disputes_manage = "payment_disputes:manage"
    payouts_read = "payouts:read"
    payouts_approve = "payouts:approve"
    fraud_risk_read = "fraud_risk:read"
    fraud_risk_manage = "fraud_risk:manage"
    reconciliation_read = "reconciliation:read"
    reconciliation_manage = "reconciliation:manage"
    currencies_read = "currencies:read"
    currencies_manage = "currencies:manage"
    countries_read = "countries:read"
    countries_manage = "countries:manage"
    finance_reports_read = "finance_reports:read"
    payment_audit_read = "payment_audit:read"
    inventory_manage = "inventory:manage"
    coupons_write = "coupons:write"
    coupons_read = "coupons:read"

    # Marketplace settings. Permission-based: custom staff roles may receive these.
    marketplace_settings_read = "marketplace_settings:read"
    marketplace_settings_manage = "marketplace_settings:manage"

    # Marketplace finance and commissions
    commissions_read = "commissions:read"
    commissions_write = "commissions:write"
    commissions_manage = "commissions:manage"
    seller_earnings_read = "seller_earnings:read"
    wallet_read = "wallet:read"
    wallet_payout = "wallet:payout"
    wallet_manage = "wallet:manage"
    wallet_adjust = "wallet:adjust"
    refunds_read = "refunds:read"
    refunds_create = "refunds:create"
    refunds_review = "refunds:review"
    refunds_process = "refunds:process"
    analytics_admin_read = "analytics:admin_read"
    analytics_seller_read = "analytics:seller_read"
    audit_logs_read = "audit_logs:read"
    security_events_read = "security_events:read"

    # Shipping and delivery
    shipping_read = "shipping:read"
    shipping_write = "shipping:write"
    shipping_track = "shipping:track"
    shipping_manage_own = "shipping:manage_own"
    shipping_manage_all = "shipping:manage_all"

    # Logistics administration and provider operations.
    # Permission-based: custom roles can receive these without role-name checks.
    logistics_companies_read = "logistics_companies:read"
    logistics_companies_manage = "logistics_companies:manage"
    logistics_services_read = "logistics_services:read"
    logistics_services_manage = "logistics_services:manage"
    logistics_zones_read = "logistics_zones:read"
    logistics_zones_manage = "logistics_zones:manage"
    logistics_rates_read = "logistics_rates:read"
    logistics_rates_manage = "logistics_rates:manage"
    logistics_integrations_read = "logistics_integrations:read"
    logistics_integrations_manage = "logistics_integrations:manage"
    logistics_shipments_read = "logistics_shipments:read"
    logistics_shipments_update = "logistics_shipments:update"

    # Existing store permissions used by current routers.
    view_own_store = "view_own_store"
    update_own_store = "update_own_store"
    upload_store_logo = "upload_store_logo"
    upload_store_banner = "upload_store_banner"
    can_view_public_stores = "can_view_public_stores"
    manage_all_stores = "manage_all_stores"

    # Granular store permissions used by gallery/opening-hours endpoints.
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




class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    hidden = "hidden"
    reported = "reported"


class ReviewReportReason(str, enum.Enum):
    spam = "spam"
    abusive = "abusive"
    misleading = "misleading"
    inappropriate = "inappropriate"
    conflict_of_interest = "conflict_of_interest"
    other = "other"


class SellerOrderStatus(str, enum.Enum):
    new = "new"
    accepted = "accepted"
    processing = "processing"
    ready_to_ship = "ready_to_ship"
    shipped = "shipped"
    delivered = "delivered"
    cancellation_requested = "cancellation_requested"
    cancelled = "cancelled"


class LogisticsCompanyStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    suspended = "suspended"
    inactive = "inactive"


class LogisticsScope(str, enum.Enum):
    local = "local"
    international = "international"
    both = "both"


class LogisticsIntegrationAuthType(str, enum.Enum):
    none = "none"
    api_key = "api_key"
    bearer = "bearer"
    basic = "basic"
    oauth2 = "oauth2"
    custom = "custom"


class ShippingRateType(str, enum.Enum):
    flat = "flat"
    weight_based = "weight_based"
    free = "free"



class DeliveryStatus(str, enum.Enum):
    created = "created"
    awaiting_pickup = "awaiting_pickup"
    courier_assigned = "courier_assigned"
    picked_up = "picked_up"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    delivery_failed = "delivery_failed"
    cancelled = "cancelled"
    returned = "returned"

class ShipmentStatus(str, enum.Enum):
    pending = "pending"
    ready_for_dispatch = "ready_for_dispatch"
    dispatched = "dispatched"
    in_transit = "in_transit"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    delivery_failed = "delivery_failed"
    returned_to_sender = "returned_to_sender"
    cancelled = "cancelled"


class InventoryReservationStatus(str, enum.Enum):
    active = "active"
    committed = "committed"
    released = "released"
    expired = "expired"
    cancelled = "cancelled"


class CommissionScope(str, enum.Enum):
    global_rule = "global"
    category = "category"
    seller = "seller"
    product = "product"


class CommissionRuleType(str, enum.Enum):
    percentage = "percentage"
    fixed = "fixed"


class MarketplaceTransactionType(str, enum.Enum):
    sale = "sale"
    commission = "commission"
    seller_earning = "seller_earning"
    commission_reversal = "commission_reversal"
    refund = "refund"
    adjustment = "adjustment"
    payout = "payout"


class WalletTransactionType(str, enum.Enum):
    sale_credit = "sale_credit"
    funds_release = "funds_release"
    payout_hold = "payout_hold"
    payout_completed = "payout_completed"
    payout_released = "payout_released"
    refund_debit = "refund_debit"
    adjustment = "adjustment"


class PayoutStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"
    cancelled = "cancelled"


class RefundStatus(str, enum.Enum):
    requested = "requested"
    under_review = "under_review"
    approved = "approved"
    processing = "processing"
    completed = "completed"
    rejected = "rejected"
    failed = "failed"
    cancelled = "cancelled"


class RefundReason(str, enum.Enum):
    changed_mind = "changed_mind"
    damaged = "damaged"
    defective = "defective"
    wrong_item = "wrong_item"
    not_received = "not_received"
    duplicate_payment = "duplicate_payment"
    other = "other"


class InventoryMovementType(str, enum.Enum):
    refund_restock = "refund_restock"
    refund_damaged = "refund_damaged"
    manual_adjustment = "manual_adjustment"
    restock = "restock"
    manual_correction = "manual_correction"
    damaged = "damaged"
    lost = "lost"
    returned = "returned"
    order_cancelled = "order_cancelled"
    warehouse_transfer = "warehouse_transfer"


class AuditSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class SecurityEventType(str, enum.Enum):
    authentication_failed = "authentication_failed"
    authorization_denied = "authorization_denied"
    suspicious_request = "suspicious_request"
    sensitive_action = "sensitive_action"


class NotificationChannel(str, enum.Enum):
    in_app = "in_app"
    email = "email"
    sms = "sms"
    push = "push"


class NotificationDeliveryStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    cancelled = "cancelled"


class NotificationEvent(str, enum.Enum):
    order_placed = "order_placed"
    payment_confirmed = "payment_confirmed"
    order_accepted = "order_accepted"
    order_dispatched = "order_dispatched"
    delivery_updated = "delivery_updated"
    order_delivered = "order_delivered"
    refund_updated = "refund_updated"
    promotion_available = "promotion_available"
    review_reply = "review_reply"
    new_order = "new_order"
    low_stock = "low_stock"
    product_reviewed = "product_reviewed"
    cancellation_requested = "cancellation_requested"
    payout_updated = "payout_updated"
    seller_approval_required = "seller_approval_required"
    product_approval_required = "product_approval_required"
    system_alert = "system_alert"


class QuestionStatus(str, enum.Enum):
    pending = "pending"
    published = "published"
    hidden = "hidden"
    rejected = "rejected"


class QuestionReportReason(str, enum.Enum):
    spam = "spam"
    abusive = "abusive"
    misleading = "misleading"
    inappropriate = "inappropriate"
    other = "other"
