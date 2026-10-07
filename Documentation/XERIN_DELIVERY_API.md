# Xerin Express — External Delivery Service Contract

Xerin Marketplace has **Xerin Express built in as the default carrier**.
Customers never pick a shipping company at checkout — the platform
auto-selects Xerin Express (Standard or Express tier) and, when a seller
marks an order *ready for pickup*, the backend calls **your delivery
service** automatically.

This document is the contract your external delivery service must
implement.

---

## 1. Environment configuration (marketplace server)

Set these in `backend/BACKEND/.env`:

```env
DELIVERY_PROVIDER_NAME=xerin-express
DELIVERY_API_BASE_URL=https://your-delivery-service.com/api
DELIVERY_API_KEY=<api-key-your-service-issues>
DELIVERY_API_KEY_HEADER=Authorization          # header name the key goes into
DELIVERY_WEBHOOK_SECRET=<long-random-string>   # you sign webhooks with this
DELIVERY_QUOTE_PATH=/quotes
DELIVERY_CREATE_PATH=/deliveries
DELIVERY_API_TIMEOUT_SECONDS=30
PUBLIC_BASE_URL=https://api.xerinmarketplace.com
```

> If `DELIVERY_API_BASE_URL` is empty, dispatch is skipped silently —
> orders still work, deliveries just are not requested externally.

---

## 2. Endpoints YOUR service must implement

### 2.1 Create a delivery — `POST {DELIVERY_API_BASE_URL}/deliveries`

Called automatically when a seller marks an order **ready to ship**
(or manually via `POST /api/v1/delivery/seller-orders/{id}/request`).

**Headers:**

```
Content-Type: application/json
Authorization: <DELIVERY_API_KEY>        # or whatever DELIVERY_API_KEY_HEADER names
```

**Request body we send:**

```json
{
  "order_reference": "<uuid>",
  "seller_order_reference": "<uuid>",
  "pickup": {
    "name": "Seller business name",
    "phone": "+255...",
    "email": "seller@shop.tz",
    "country": "Tanzania",
    "region": "Dar es Salaam",
    "city": "Dar es Salaam",
    "address": "Street / building"
  },
  "dropoff": {
    "name": "Customer name",
    "phone": "+255...",
    "country": "Tanzania",
    "region": "Dar es Salaam",
    "district": "Ilala",
    "ward": "Upanga",
    "city": "Dar es Salaam",
    "address": "Street, building, house",
    "landmark": "Near ...",
    "postal_code": "11101",
    "latitude": -6.7924,
    "longitude": 39.2083
  },
  "package": {
    "item_count": 3,
    "description": "Product A, Product B",
    "declared_value": "40000.00",
    "currency": "TZS"
  },
  "callback_url": "https://api.xerinmarketplace.com/api/v1/delivery/webhooks/xerin-express"
}
```

**Response we expect (200/201):**

```json
{
  "delivery_id": "uuid-or-string",      // required — or "id"
  "tracking_number": "XE-10245",        // optional
  "tracking_url": "https://...",        // optional
  "delivery_fee": 5000,                 // optional number
  "currency": "TZS",                    // optional
  "courier_name": "John",               // optional
  "courier_phone": "+255...",           // optional
  "estimated_pickup_at": "ISO-8601",    // optional
  "estimated_delivery_at": "ISO-8601"   // optional
}
```

`delivery_id` (or `id`) is **required** — everything else optional.

### 2.2 Quote a delivery — `POST {DELIVERY_API_BASE_URL}/quotes`

Manual endpoint (used internally / by sellers):

```json
// we send:
{ "pickup": {...}, "dropoff": {...}, "package": {...}, "currency": "TZS" }

// you return:
{ "fee": 5000, "quote_id": "...", "estimated_pickup_at": "...", "estimated_delivery_at": "..." }
```

`fee` (or `amount`) is required.

---

## 3. Status webhooks — YOUR service calls OURS

Whenever a delivery changes state, call the `callback_url` you received:

```
POST https://api.xerinmarketplace.com/api/v1/delivery/webhooks/xerin-express
Content-Type: application/json
X-Delivery-Signature: sha256=<HMAC-SHA256 hex of the RAW request body, key = DELIVERY_WEBHOOK_SECRET>
```

**Body:**

```json
{
  "delivery_id": "the-id-you-returned-in-2.1",
  "status": "courier_assigned",
  "tracking_number": "XE-10245",
  "tracking_url": "https://...",
  "courier_name": "John",
  "courier_phone": "+255...",
  "location": "Current hub / area",
  "notes": "Free text",
  "failure_reason": "if failed/cancelled"
}
```

**Allowed `status` values:**

| You send | Shipment becomes |
|---|---|
| `created`, `awaiting_pickup`, `courier_assigned` | ready_for_dispatch |
| `picked_up` | dispatched |
| `in_transit` | in_transit |
| `out_for_delivery` | out_for_delivery |
| `delivered` | delivered (+ seller order → delivered) |
| `delivery_failed` | delivery_failed |
| `cancelled` | cancelled |
| `returned` | returned_to_sender |

We reply `200 {"accepted": true, "delivery_id": "...", "status": "..."}` —
anything else means we rejected it (`401` bad signature, `404` unknown
delivery, `422` bad payload).

---

## 4. The full chain

```
Seller: ready_to_ship
        ↓  marketplace POST /deliveries → your service
Your service assigns a rider
        ↓  POST /delivery/webhooks/xerin-express (status=...)
Shipment tracks: ready_for_dispatch → dispatched → in_transit
              → out_for_delivery → delivered
Customer sees live tracking on the Track page.
```

Minimum viable implementation: one `POST /deliveries` endpoint returning
`{ "delivery_id": "..." }`, plus webhook calls on status changes.
