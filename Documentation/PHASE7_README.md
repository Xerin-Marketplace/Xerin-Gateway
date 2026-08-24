# Phase 7 — Logistics Country Dropdown + Route Capabilities

## Frontend
Coverage Zone country is now a dropdown backed by the backend ISO country list.
No more free-text values like UAE / UAE COUNTRY / U.A.E.

The company independently ticks:
- Domestic delivery within this country
- Cross-border inbound: foreign country -> this country
- Cross-border outbound: this country -> foreign country

At least one must be selected.

## Backend
New:
GET /api/v1/logistics/country-options

ShippingZone create/update canonicalizes country names even if an API client sends an alias.
Eligibility comparisons are alias-safe.

Examples:
UAE == United Arab Emirates
USA == United States
UK == United Kingdom
TZ == Tanzania

## Existing data migration
p45_logistics_country_normalization normalizes common aliases already saved in shipping_zones.

Run:
alembic heads
alembic current
alembic upgrade head

## UAE -> Tanzania configuration
UAE zone:
- Country: United Arab Emirates
- Cross-border outbound: YES

Tanzania zone:
- Country: Tanzania
- Cross-border inbound: YES

Each side still needs the active zone/rate/service path required by the pricing engine.

## Verify
Backend:
python -m compileall api
pytest tests/test_phase7_logistics_country_normalization.py -q
sudo systemctl restart xerin-api

Frontend:
npx tsc --noEmit --pretty false
npm run build
