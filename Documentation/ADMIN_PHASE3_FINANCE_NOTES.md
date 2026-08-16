# Admin Phase 3 — Finance Configuration

This phase completes the Admin finance foundation while reusing the payment infrastructure already added in p6.

## Existing finance/payment components reused

- AzamPay payment integration
- `payment_provider_configs`
- `payment_currencies`
- `payment_fx_rates`
- `payment_countries`
- `payments`
- `payment_transactions`
- `seller_wallets`
- `wallet_transactions`
- `seller_payout_accounts`
- `payout_requests`
- commission rules
- refunds
- reconciliation
- payment audit logs

## Phase 3 additions

### Finance settings

`finance_settings` is a singleton configuration for:

- default payment provider
- settlement currency
- minimum payout amount
- payout fee type/value
- payout processing days
- automatic payout enable/disable
- escrow enable/disable
- automatic escrow release enable/disable
- partial release enable/disable
- commission hold behavior

### Escrow finance foundation

New tables:

- `escrow_holds`
- `escrow_events`

The escrow model does not use a single mutable "Xerin balance". Each hold preserves:

- payment
- order / order item
- seller
- gross customer amount
- seller entitlement
- Xerin commission
- refunded amount
- released amount
- release date / dispute / refund state
- immutable event history

Actual automatic creation of escrow holds from successful customer payments will be wired during the Customer payment/checkout phase after multi-seller order allocation is finalized. This avoids corrupting current order accounting before the seller/customer pricing flow is complete.

### FX behavior

TZS and USD continue to be database configuration records. No exchange rate is hardcoded.

`POST /api/v1/admin/finance/fx/convert` resolves the newest active rate at the requested timestamp. If only the inverse pair exists, it calculates the inverse safely.

When an active FX rate is created through the existing `/admin/fx-rates` endpoint, previous active rates for that same direction are deactivated so there is one current active rate per direction.

## RBAC

New permissions:

- `finance_settings:read`
- `finance_settings:manage`
- `escrow:read`
- `escrow:manage`
- `escrow:release`

There are no role-name checks. A future Finance Manager, Settlement Officer or Auditor role can receive only the required permissions.
