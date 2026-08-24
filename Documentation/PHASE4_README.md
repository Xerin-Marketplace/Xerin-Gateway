# Xerin Phase 4 — Customer Currency Display

## Purpose

Phase 4 adds buyer-facing display currency without changing settlement currency.

Example:
- Seller listing: 100 USD
- Admin rate: 1 USD = 2,600 TZS
- Buyer selects USD -> product can display USD 100
- Buyer selects TZS -> product displays TZS 260,000
- Buyer selects AED -> product displays the AED equivalent
- Cart/checkout/payment remain canonical TZS underneath

## Backend

Updated:
- backend/api/routers/products.py

New public endpoint:
- GET /api/v1/products/display-currencies

The endpoint returns only active currencies that are currently convertible to TZS.

Example response:
[
  {
    "code": "TZS",
    "name": "Tanzanian Shilling",
    "symbol": "TSh",
    "rate_to_tzs": "1"
  },
  {
    "code": "USD",
    "name": "US Dollar",
    "symbol": "$",
    "rate_to_tzs": "2600"
  }
]

A non-TZS currency is omitted if it has no active current CURRENCY/TZS rate.
This prevents customers selecting a display currency that cannot be converted.

No Alembic migration is required.

## Frontend currency architecture

New:
- src/app/context/CurrencyContext.tsx
- src/lib/api/endpoints/currency.ts
- src/components/shared/PriceDisplay.tsx
- src/components/Header/CurrencySelector.tsx

The selected display currency is stored in:
- localStorage key: xerin_display_currency

Conversion formula:
1. Seller/listing amount -> TZS using source rate_to_tzs
2. TZS -> selected display currency using selected rate_to_tzs

Example:
- Product = USD 100
- USD/TZS = 2600
- AED/TZS = 708

TZS value:
  100 * 2600 = 260000 TZS

AED display:
  260000 / 708 = approx. 367.23 AED

## Product prices

UI Product now preserves:
- currency

The adapter maps backend Product.currency into the storefront product model.

Product cards, search, shop details, categories, best sellers, related products,
wishlist and other key storefront product displays now use PriceDisplay.

## Cart

Phase 3 already made cart amounts canonical TZS.

Phase 4 therefore converts cart TZS values only for display:
- cart item price
- subtotal
- discounts
- cart total
- mini cart

No browser-selected currency is sent back as a settlement amount.

## Checkout

Checkout amounts are still backend TZS amounts.

The selected display currency may be shown to the buyer, but the checkout clearly
states that payment is always settled in TZS.

Grand Total can show:
  USD 100 (pay TZS 260,000)

when the buyer selected USD.

## Header

Desktop and mobile storefront headers now expose a currency selector.

Only currencies returned by the public display-currencies endpoint are selectable.

## Important safety rule

Display conversion is presentation only.

The frontend never controls:
- cart canonical amount
- order amount
- payment currency
- payment gateway amount

Those remain controlled by the Phase 3 backend in TZS.

## Deployment

Backend:
    cd /var/Xerin-Gateway/BACKEND
    source .venv/bin/activate
    python -m compileall api
    sudo systemctl restart xerin-api

Frontend:
    npx tsc --noEmit --pretty false
    npm run build

Then redeploy/restart the frontend and hard-refresh the browser.

## Suggested test

Admin:
    USD/TZS = 2600
    AED/TZS = 708

Seller:
    Product = USD 100

Buyer:
1. Select USD -> product should show about USD 100
2. Select TZS -> product should show about TZS 260,000
3. Select AED -> product should show about AED 367.23
4. Add product to cart
5. Change display currency several times
6. Cart totals should change visually only
7. Checkout must still indicate TZS as the actual payment/settlement amount

## Phase boundary

This phase does not create permanent FX snapshots on completed orders.
That remains Phase 5 — Checkout & Financial FX Snapshot Protection.
