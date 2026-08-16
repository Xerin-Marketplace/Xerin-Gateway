# Seller Phases 1–10 — Backend Update

This package completes the backend foundation for the ten Seller phases discussed.

## Phase 1 — Commission-aware product pricing

- Seller-entered `price` is treated as seller base price on create/update.
- Existing storefront-facing `products.price` remains customer/marketplace price for compatibility.
- Product and variant records now preserve:
  - seller base price
  - seller sale price
  - commission rate snapshot
  - commission amount snapshot
  - customer marketplace price
- Pricing uses Admin Marketplace Settings commission precedence:
  Product → Seller → Category → Global.
- New preview endpoint:
  `POST /api/v1/seller/pricing/preview`

## Phase 2 — Payout account

Existing payout accounts are extended with:
- active/inactive
- pending/verified/rejected verification
- provider reference
- verified timestamp
- safe deactivation when payout history exists

Seller payout requests now require a verified active payout account and respect Finance minimum payout configuration.

## Phase 3 — Promotions

Existing seller promotions are retained and refined:
- server-side pagination/search
- seller-funded promotion marker
- seller cannot attach a promotion to another seller's product

Marketplace commission is not reduced in this phase; promo allocation into checkout will be finalized during Customer checkout.

## Phase 4 — Seller orders

Existing SellerOrder lifecycle remains authoritative and already supports pagination/status/search/fulfillment transitions.

## Phase 5 — Order chat

New tables:
- seller_order_messages
- seller_order_message_attachments

Seller endpoints:
- GET `/api/v1/seller/orders/{seller_order_id}/messages`
- POST `/api/v1/seller/orders/{seller_order_id}/messages`

Customer/Xerin/logistics participation can be added to the same thread during their respective role phases.

## Phase 6 — Packaging / Ready for pickup

New:
- seller_order_packages
- seller_order_package_attachments

Seller must prepare and confirm package data before marking a SellerOrder ready-to-ship.

## Phase 7 — Seller wallet

Existing wallet architecture is retained:
- pending
- available
- reserved
- paid out
- refunded
- debt

Wallet transaction history is now paginated.

Actual escrow-to-wallet credit remains deferred until Customer payment allocation is finalized.

## Phase 8 — Payout requests

Seller payout history is now paginated.
Payout request checks:
- payout account belongs to seller
- payout account active
- payout account verified
- Finance minimum payout threshold

## Phase 9 — Reviews / Q&A

Existing seller review and product-Q&A routers remain in place. Seller dashboard now includes average rating, review count and unanswered questions.

## Phase 10 — Dashboard / performance

New endpoint:
`GET /api/v1/seller/dashboard`

Returns operational seller KPIs for:
- products
- promotions
- orders
- wallet
- payouts
- reviews
- unanswered questions

## Important future dependency

Do not automatically release escrow into seller wallet yet. The Customer phase must first finalize:
- multi-seller cart allocation
- promo allocation
- shipping allocation
- payment success
- customer confirmation/dispute rules

That prevents incorrect financial balances.
