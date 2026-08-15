# Xerin Payment Administration integration notes

## AzamPay patch review

The uploaded `azampay_patch` is an older patch relative to the uploaded BACKEND tree. Its core integration is already present in BACKEND:

- `api/services/azampay_service.py`
- `api/routers/payments.py`
- AzamPay settings in `api/config.py` and `.env.example`
- `tests/test_azampay_integration.py`

The current BACKEND also contains a newer mobile-money name lookup addition that is not in the patch. Therefore the patch should **not** be copied wholesale over BACKEND because it would remove newer auth/OTP/RBAC/catalog/support changes from shared files such as `api/schemas.py` and `api/config.py`.

This update keeps the current BACKEND as the source of truth, preserves the AzamPay integration, and fixes the name-lookup error path.

## Payment administration architecture

Existing marketplace finance models are reused:

- `payments` and `payment_transactions` for customer/provider transactions
- `refunds` for refund lifecycle
- `commission_rules` and `order_item_commissions` for fees/commissions
- `seller_wallets`, `wallet_transactions`, `payout_requests`, and `payout_events` for seller settlement
- `audit_logs` for payment audit reporting

New tables are added only for capabilities that did not already exist:

- `payment_provider_configs`
- `payment_currencies`
- `payment_fx_rates`
- `payment_countries`
- `payment_disputes`
- `payment_risk_events`
- `payment_reconciliation_records`

The migration seeds the currently integrated provider `AzamPay`, and creates TZS and USD currency configuration rows. It intentionally does **not** seed a TZS/USD exchange rate. FX rates must be inserted from an approved source or by an authorized finance user.

## RBAC

No endpoint checks a role name such as `admin`. Every payment administration operation is protected through permissions. This means future custom roles such as Finance Manager, Payment Officer, Settlement Officer, Risk Officer, or Auditor can use the same endpoints when the required permissions are assigned.

## Deployment

Before migration, confirm the current database revision is `p5_support_tickets`, then run:

```bash
python -m py_compile api/enums.py api/models.py api/schemas.py \
  api/routers/payments.py api/routers/payment_admin.py \
  api/services/azampay_service.py api/main.py api/seed_permissions.py \
  alembic/versions/p6_payment_admin.py

alembic heads
alembic current
alembic upgrade head
python -m api.seed_permissions
```

Then restart the API service.
