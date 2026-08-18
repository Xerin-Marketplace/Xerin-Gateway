Xerin Phase 12 Task 3 - Public Active Advertisement API

Public endpoints (no authentication):
GET /api/v1/advertisements/active
GET /api/v1/advertisements/slot/{placement}
GET /api/v1/advertisements/slots

Live rule:
status = active
AND starts_at <= current UTC instant
AND ends_at > current UTC instant

At ends_at exactly, the advertisement is no longer returned.

Fallback behavior:
GET /advertisements/slot/{placement}
returns:
{
  "placement": "hero_side_top",
  "advertisement": null
}
when no live campaign exists. The frontend can therefore keep the current
Top-rated sellers / Xerin Logistics template cards.

Priority:
If several active advertisements compete for a placement, the highest priority
wins. Newer created_at breaks a priority tie.

Homepage optimization:
GET /advertisements/slots resolves hero_side_top and hero_side_bottom in one API
request by default.

Privacy:
Public responses intentionally do NOT expose price, billing_type, counters,
metadata, created_by_id, or updated_by_id.

Caching:
Public advertisement responses use Cache-Control: no-store so a stale browser/CDN
cannot display an ad beyond ends_at or delay a newly-started campaign.

No Alembic migration is required for Task 3.
Frontend integration is intentionally deferred to the later homepage placement task.
