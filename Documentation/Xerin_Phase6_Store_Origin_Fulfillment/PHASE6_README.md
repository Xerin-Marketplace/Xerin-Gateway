# Phase 6 — Store-Origin Fulfillment & Shipment Splitting

## Why this phase is required
The old fulfillment code grouped paid order items only by `seller_id`. That is no longer correct because one seller can own multiple stores in different physical locations/countries. A cart containing two products from two stores owned by the same seller must create two fulfillment origins.

## New source of truth
Order item -> seller + store -> seller order -> shipment.

A seller with Store A (Tanzania) and Store B (UAE) can now receive two seller orders and two shipments under the same customer order. Each shipment preserves the store origin used by the Phase 5 delivery quote.

## Database migration
`p44_store_origin_fulfillment.py`
- adds required `store_id` to `order_items`
- adds required `store_id` to `seller_orders`
- adds required `store_id` to `shipments`
- backfills historical rows from each product's assigned store
- changes seller-order uniqueness from `(order_id, seller_id)` to `(order_id, seller_id, store_id)`
- changes shipment uniqueness the same way

Run:
    alembic upgrade head

## Backend behavior
- Order creation snapshots the product's store into each OrderItem.
- Payment confirmation groups fulfillment by `(seller_id, store_id)`.
- Seller Orders display only items from that exact store origin.
- Seller Fulfillment resolves the shipment belonging to that exact store.
- Workflow reconciliation and delivery OTP completion match seller orders by seller + store.
- Product review delivery validation uses the order item's store origin.

## API/UI contracts
Shipment, OrderItem, CustomerSellerOrderSummary and seller order responses now expose `store_id`. Seller order views additionally expose `store_name` and `store_country`.

## Verify
Backend:
    alembic upgrade head
    python -m compileall api
    pytest tests/test_phase6_store_origin_fulfillment.py -q
    sudo systemctl restart xerin-api
    sudo journalctl -u xerin-api -n 100 --no-pager

Frontend:
    npx tsc --noEmit --pretty false
    npm run build

## Critical acceptance test
Use one seller owning two stores. Put one product from each store into one cart, pay the order, then verify:
- 1 parent customer order
- 2 seller orders for the same seller, each with a different store_id
- 2 shipments, each with the matching store_id
- each seller order contains only the items from its own store
- each shipment continues independently through pickup/tracking/delivery
