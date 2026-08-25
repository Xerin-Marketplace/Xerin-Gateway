# Phase 14 — Task 4: Payment Success Page + Downloadable Receipt

## Backend

New endpoint:

    GET /api/v1/orders/{order_id}/receipt.pdf

Receipt security:
- Requires authenticated order owner or privileged order operator.
- Requires a Payment row whose status is VERIFIED `completed`.
- Returns HTTP 409 if the payment is pending, processing, failed or cancelled.
- Receipt is generated from the completed Payment + immutable Order record.
- No database migration is required.

Receipt contains:
- Receipt number
- Order number
- Xerin payment reference
- Provider transaction reference
- Payment method
- Payment provider
- Paid date/time
- Status PAID
- Amount paid
- Order total

Invoice and receipt are intentionally separate:
- Invoice = what was charged.
- Receipt = proof the payment completed.

## Frontend

### Dedicated payment success page

New route:

    /payment-success/{orderId}

It has no marketplace header/footer/chatbot.

When `/order-success/{orderId}` detects a backend-verified `completed` payment,
it automatically redirects to the clean successful-payment page.

The page displays:
- Payment Successful
- verified status
- amount paid
- payment method
- payment transaction reference
- paid timestamp
- Download Receipt
- Download Invoice
- View Order
- Continue Shopping

The page refuses to present itself as successful if
`/payments/orders/{orderId}/state` is not `completed`.

### Buyer Order Details

If `payment_status === completed`, the customer's order detail page now shows:

    Download Receipt

beside the existing Download Invoice action.

## Deploy backend

    cd /var/Xerin-Gateway/BACKEND
    source .venv/bin/activate
    python -m compileall api
    pytest tests/test_phase14_task4_payment_receipt.py -q
    sudo systemctl restart xerin-api
    sudo journalctl -u xerin-api -n 100 --no-pager

No Alembic migration for Task 4.

## Deploy frontend

    npx tsc --noEmit --pretty false
    npm run build

## Acceptance test

1. Create checkout and start Mobile Payment/Card Payment.
2. Provider callback must verify and change Payment -> completed.
3. Order-success polling sees completed.
4. Browser redirects to:
       /payment-success/{orderId}
5. Verify amount/reference/date.
6. Download Receipt.
7. Download Invoice.
8. Open Account -> Orders -> same order.
9. Verify Download Receipt appears there too.
10. Try receipt endpoint for an unpaid order:
       expected HTTP 409 payment_receipt_not_available.
