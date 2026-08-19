Xerin Phase 2 Task 8 - Customer Multi-Seller Shipment Tracking

Goal:
Give the customer one order-level tracking view while preserving independent
shipment state for every seller.

New endpoints:

GET /api/v1/orders/{order_id}/tracking

Query:
- page
- page_size
- search
- status
- requires_action

Search covers:
- shipment id
- seller business name
- logistics company name
- carrier name
- tracking number
- product names

Response contains:
- order-level summary
- overall tracking state/progress
- counts by shipment state
- customer-action counters
- paginated seller shipments
- seller/logistics identity
- product items
- pickup proof state
- latest tracking event
- latest 5 tracking events

Full shipment event history:

GET /api/v1/orders/{order_id}/tracking/shipments/{shipment_id}/events

Query:
- page
- page_size

Multi-seller example:
Order XR1001
  Seller A -> Picked up / pickup proof approved
  Seller B -> Ready for pickup
  Seller C -> Pickup proof pending customer review

Overall order remains one customer order, while each seller shipment tracks
independently.

Pickup proof integration:
- expired pending proofs are normalized to auto_approved when tracking is read;
- pending/disputed proof state surfaces requires_customer_action=true;
- Task 8 does NOT release seller money.

Why no migration:
This is an aggregate/read-model API built from existing:
- orders
- shipments
- shipment_items
- shipment_tracking_events
- shipment_pickup_proofs
- sellers
- logistics_companies

No new persistent data is required.

Phase 2 is complete after this task.
