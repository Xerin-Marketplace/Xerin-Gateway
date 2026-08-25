# Phase 14 — Task 3: Unpaid Order Expiry + Inventory Release + Cancellation Email

## Lifecycle

A NEW checkout order receives:

    payment_due_at = now + PAYMENT_ORDER_TIMEOUT_MINUTES

Default:
    PAYMENT_ORDER_TIMEOUT_MINUTES=5

If the order is still `pending` when that deadline passes:

1. Lock active payment attempts.
2. Lock the order.
3. If any payment is already `completed`, DO NOT cancel.
4. Mark pending/processing attempts as `cancelled`.
5. Release ACTIVE inventory reservations.
6. Mark the order `cancelled`.
7. Write OrderStatusHistory.
8. Commit the database transaction.
9. Send the customer a cancellation email.
10. Persist cancellation_email_sent_at after successful SMTP delivery.

Email failure does not undo inventory/order cancellation. The next worker run retries the email.

## Idempotency

Order fields:
- payment_due_at
- cancelled_at
- cancellation_reason
- cancellation_email_sent_at

Payment timeout transactions use a stable unique idempotency key:
    order-timeout:<order_id>:<payment_id>

Released reservations are only rows still in ACTIVE status.

## Race safety

The worker locks Payment rows before Order, matching the payment callback lock order.
A completed payment found under lock wins over timeout cancellation.

After cancellation, existing payment callback rules refuse a `cancelled` order from
being silently moved to paid.

IMPORTANT: choose a production timeout that is longer than the normal payment-provider
authorization window. 5 minutes is useful for development. 10–15 minutes is safer
for many production MNO/card flows.

## Migration

    alembic heads
    alembic current
    alembic upgrade head

Migration:
    p46_unpaid_order_expiry

It does NOT backfill deadlines onto old orders. This avoids cancelling historical
pending orders immediately after deployment. Only newly created checkout orders get
a payment deadline.

## Configure

In backend .env:

    PAYMENT_ORDER_TIMEOUT_MINUTES=5

For production you may later use:

    PAYMENT_ORDER_TIMEOUT_MINUTES=15

## Manual worker test

    cd /var/Xerin-Gateway/BACKEND
    source .venv/bin/activate
    python -m api.scripts.expire_unpaid_orders

Example output:

    Unpaid-order expiry: cancelled=1 reservations_released=1 paid_skipped=0 emails_sent=1 email_failures=0

## Run automatically every minute with systemd

Copy:

    ops/systemd/xerin-unpaid-order-expiry.service
    -> /etc/systemd/system/xerin-unpaid-order-expiry.service

    ops/systemd/xerin-unpaid-order-expiry.timer
    -> /etc/systemd/system/xerin-unpaid-order-expiry.timer

Then:

    sudo systemctl daemon-reload
    sudo systemctl enable --now xerin-unpaid-order-expiry.timer
    systemctl status xerin-unpaid-order-expiry.timer --no-pager
    systemctl list-timers --all | grep xerin-unpaid

Worker logs:

    journalctl -u xerin-unpaid-order-expiry.service -f

## Backend verification

    python -m compileall api
    pytest tests/test_phase14_task3_unpaid_order_expiry.py -q
    sudo systemctl restart xerin-api

## Frontend

Order-success now has a dedicated timeout state:

    Order cancelled — payment window expired

It tells the customer that reserved stock was released and does not offer Retry
Payment on an expired order.

Build:

    npx tsc --noEmit --pretty false
    npm run build

## SMTP

Cancellation emails use the existing EMAIL_* settings. Make sure EMAIL_HOST,
EMAIL_USER/EMAIL_PASSWORD and EMAIL_FROM are configured.

## Acceptance test

1. Set PAYMENT_ORDER_TIMEOUT_MINUTES=5.
2. Checkout an item and initiate Mobile/Card payment.
3. Do NOT approve payment.
4. Wait beyond 5 minutes and allow the timer to run.
5. Verify:
   - orders.status = cancelled
   - orders.cancellation_reason = payment_confirmation_timeout
   - payments pending/processing -> cancelled
   - active inventory reservation -> cancelled
   - Inventory.reserved_quantity decreases
   - Inventory.available_quantity increases
   - status history contains automatic cancellation
   - customer receives email
   - order-success page shows timeout cancellation state.
