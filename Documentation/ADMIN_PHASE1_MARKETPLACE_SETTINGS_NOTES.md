# Admin Phase 1 — Marketplace Settings

This update completes the backend foundation for the first Admin phase while reusing the existing commission engine.

## Scope implemented

- Default/global commission rule
- Category-specific commission rule
- Seller-specific commission rule
- Product-specific commission override
- Fixed precedence: product > seller > category > global
- Escrow release period setting
- Dispute period setting
- COD enabled/disabled setting
- International delivery enabled/disabled setting
- Search + server-side pagination for commission rules
- Commission pricing preview for the future Seller pricing screen
- Permission-based access (no hard-coded admin role checks)

## Important pricing rule

The pricing preview follows the business rule agreed for the next Seller phase:

seller base price + Xerin commission = customer display price

Example: 200 TZS base price + 2% = 204 TZS customer price.

The existing order commission engine is intentionally not rewritten in this phase because current product/order records do not yet store separate seller-base-price and customer-price snapshots. That wiring belongs to the Seller commission-aware product pricing phase, preventing a breaking change to existing orders.

## Endpoints

- GET /api/v1/admin/marketplace-settings
- PUT /api/v1/admin/marketplace-settings
- GET /api/v1/admin/marketplace-settings/commission-rules
- POST /api/v1/admin/marketplace-settings/commission-rules
- PATCH /api/v1/admin/marketplace-settings/commission-rules/{rule_id}
- DELETE /api/v1/admin/marketplace-settings/commission-rules/{rule_id}
- POST /api/v1/admin/marketplace-settings/commission-preview

## Permissions

- marketplace_settings:read
- marketplace_settings:manage
- commissions:read
- commissions:manage

These can be assigned to any custom RBAC role. Role names are not checked by the router.

## Migration

p7_marketplace_settings, after p6_payment_admin.

The settings table is a database-enforced singleton. No business-policy values are inserted automatically: the Admin must explicitly configure release periods and feature flags.
