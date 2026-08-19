# Completion Phase 1 Task 1 — Trusted seller settlement

Seller funds now become available only after the shipment has all three trusted checkpoints:

1. seller-confirmed physical handover;
2. pickup proof linked to the same shipment and seller; and
3. customer approval or configured auto-approval.

The release is scoped through `shipment_items`, so approval of one seller shipment cannot release another seller's entitlement. Disputed pickup evidence marks unreleased holds disputed. Manual, receipt-based, and timed release paths can no longer bypass trusted pickup verification.

Run:

```bash
alembic upgrade head
python -m compileall api
uvicorn api.main:api --reload
```

Expected Alembic head: `p33_trusted_seller_settlement`.
