Xerin Phase 12 Task 1 - Advertisement Foundation

Implemented:
- Advertisement model
- exact timezone-aware starts_at and ends_at
- automatic time-derived expiry (no cleanup/scheduler required to hide expired ads)
- effective statuses: draft, scheduled, active, paused, expired
- placements:
    hero_side_top
    hero_side_bottom
    homepage_banner
    category_banner
    search_banner
- title, description, image, optional mobile image, alt text
- CTA label and target URL
- advertiser name
- priority for competing ads
- fixed/CPC/CPM billing foundation
- price and currency foundation
- impression/click aggregate counters
- metadata JSON
- admin creator/updater audit IDs
- database constraints and live-slot index

Important automatic-expiry rule:
An advertisement is live only when:
    status = active
    AND starts_at <= NOW()
    AND ends_at > NOW()

Therefore at the exact ends_at timestamp it disappears from future public API
results even if its stored status remains "active". No background job is required
for storefront removal.

Alembic:
The uploaded backend had TWO source heads:
- p13_payment_callback_idempotency
- p3_search_recommendations

p14_advertising_foundation intentionally merges both heads and becomes the
single new head.

Run:
    alembic heads
    alembic upgrade head
    alembic current

Expected new head:
    p14_advertising_foundation

No frontend changes are required for Task 1.
