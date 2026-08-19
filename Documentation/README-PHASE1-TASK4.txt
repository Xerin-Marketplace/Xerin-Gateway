Xerin Logistics Roadmap - Phase 1 Seller - Task 4
Package Preparation Enhancement

New migration:
  p17_seller_package_preparation
  down_revision = p16_seller_pickup_locations

New scalable seller package endpoints:
  GET    /api/v1/seller/orders/{seller_order_id}/packages
  POST   /api/v1/seller/orders/{seller_order_id}/packages
  GET    /api/v1/seller/orders/{seller_order_id}/packages/{package_id}
  PATCH  /api/v1/seller/orders/{seller_order_id}/packages/{package_id}
  DELETE /api/v1/seller/orders/{seller_order_id}/packages/{package_id}

List supports:
  page, page_size, search, is_ready, package_type

Legacy compatibility retained:
  GET /api/v1/seller/orders/{seller_order_id}/package
  PUT /api/v1/seller/orders/{seller_order_id}/package

Package fields added:
  package_label
  package_type: parcel|box|envelope|crate|pallet|other
  contents_summary
  fragile
  keep_upright
  temperature_sensitive
  handling_instructions
  declared_value
  declared_currency
  sealed_at

Existing fields retained:
  weight_kg, length_cm, width_cm, height_cm, package_count,
  notes, is_ready, prepared_at, attachments

Readiness change:
  READY_TO_SHIP now evaluates every package record for the seller order.
  All package groups must be ready and all must have positive weight.
  Dimensions remain a non-blocking warning for now.

Immutability:
  Package create/update/delete is blocked once the seller order reaches
  ready_to_ship or a later fulfillment state.

No new permissions required; existing seller_packaging:manage is used.

Deployment:
  alembic heads
  alembic upgrade head
  alembic current
  pytest tests/test_phase1_task4_package_preparation.py -v
