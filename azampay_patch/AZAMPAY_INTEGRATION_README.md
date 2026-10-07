# AzamPay integration

This backend supports:

- Mobile-money push checkout through AzamPay MNO checkout.
- Card payments through AzamPay hosted checkout. Card numbers, CVV and expiry are never sent to Xerin.
- AzamPay callback processing into the existing payment/order/inventory/commission flow.

## Initiate mobile money

`POST /api/v1/payments/initiate`

```json
{
  "order_id": "ORDER_UUID",
  "method": "mobile_money",
  "provider": "Airtel",
  "phone_number": "2557XXXXXXXX"
}
```

Accepted MNO aliases include Airtel/Airtel Money, Tigo/Tigo Pesa/Mixx, Halopesa, Azampesa, and Mpesa/Vodacom.

## Initiate card

`POST /api/v1/payments/initiate`

```json
{
  "order_id": "ORDER_UUID",
  "method": "card",
  "provider": "azampay",
  "success_url": "https://frontend.example/payment/success",
  "failure_url": "https://frontend.example/payment/failed"
}
```

Read the redirect URL from `provider_response.checkout_url` and redirect the browser there.

## Callback

Register this URL in the AzamPay merchant/developer portal:

`POST https://YOUR_API/api/v1/payments/azampay/callback`

When `AZAMPAY_CALLBACK_SECRET` is set, the callback must include the same value in `X-AzamPay-Secret`. If AzamPay cannot add custom headers, protect the callback at your reverse proxy or confirm the current webhook-signature mechanism with AzamPay before production.

## Environment

Copy the AzamPay section from `.env.example` into `.env` and fill in credentials issued by AzamPay.

No database migration is required for this integration because it uses the existing `payments` and `payment_transactions` tables.
