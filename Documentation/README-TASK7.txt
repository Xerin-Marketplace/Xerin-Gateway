Xerin x AzamPay - Task 7
Callback idempotency and duplicate-event protection

Implemented:
- payment_transactions.idempotency_key
- unique PostgreSQL index for event fingerprints
- stable provider/payment/transaction/status callback key
- duplicate callbacks return harmlessly without repeating side effects
- processing -> completed remains allowed as distinct events
- failed/cancelled callback replays do not duplicate order history
- amount-mismatch callback replays do not spam audit rows
- payment row locking + DB unique key protect concurrent replays
- PaymentTransaction response exposes idempotency_key for audit

Migration:
p12_customer_checkout_snapshot -> p13_payment_callback_idempotency

Run:
alembic upgrade head

Frontend changes:
None.
