# Admin Phase 2 — Logistics Management

This phase extends the existing Xerin shipping/shipments foundation instead of replacing it.

## Existing components reused

- `shipping_zones`
- `shipping_methods`
- `shipping_rates`
- `shipments`
- `shipment_items`
- `shipment_tracking_events`
- `/shipping/quote`

## New organization layer

A Logistics Company is now separate from a login account.

- `logistics_companies`
- `logistics_company_users`

An administrator can create a normal user through RBAC and link that user to a logistics company. The role name is irrelevant; endpoint access is controlled by permissions.

## Logistics configuration

- Companies
- Services (extends ShippingMethod)
- Local / international zones
- Rates and currency
- API/webhook metadata
- Shipment workspace for logistics-company users

## Security of integration secrets

The database intentionally stores secret-manager/environment references (`credential_reference`, `webhook_secret_reference`) rather than clear-text API secrets. Actual secrets should be supplied through deployment secrets/environment or a future secret-manager adapter.

## Customer quote behavior

`POST /api/v1/shipping/quote` now:

1. Determines local Tanzania vs international from the address.
2. Enforces Marketplace Settings for international delivery.
3. Matches active zones.
4. Matches active services.
5. Excludes suspended/inactive logistics companies.
6. Returns logistics company, service, COD/tracking support, currency, rate, and ETA.

## RBAC permissions

- logistics_companies:read
- logistics_companies:manage
- logistics_services:read
- logistics_services:manage
- logistics_zones:read
- logistics_zones:manage
- logistics_rates:read
- logistics_rates:manage
- logistics_integrations:read
- logistics_integrations:manage
- logistics_shipments:read
- logistics_shipments:update

No logistics endpoint depends on a role literally named `admin` or `logistics`.
