# Xerin Phase 1 Seller Task 5 — READY_TO_SHIP Orchestration

Changes:
- READY_TO_SHIP now assigns the checkout-selected logistics company to the seller shipment.
- Creates an idempotent durable outbound `shipment.ready_for_pickup` event in `logistics_webhook_events`.
- Event snapshots pickup GPS/contact, customer dropoff, and prepared package data.
- Existing/new shipment creation now snapshots `order.logistics_company_id`.
- If a legacy order has no logistics company, the shipment remains ready_for_dispatch and a tracking event records that assignment is pending.
- No external network request is performed inside the seller transaction. Actual signed partner delivery/retry belongs to the later Partner API/Security phase.
- No Alembic migration is required.

Server validation:
python -m py_compile api/services/logistics_orchestration.py api/routers/seller_orders.py api/routers/payments.py
python -c "from api.main import app; print('FULL APP IMPORT OK')"
pytest tests/test_phase1_task5_ready_to_ship_orchestration.py -v
sudo systemctl restart xerin-api
sudo systemctl status xerin-api --no-pager
