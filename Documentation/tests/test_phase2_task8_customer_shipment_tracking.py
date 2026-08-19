from api.services.customer_shipment_tracking import (
    STATUS_LABELS,
    STATUS_PROGRESS,
)


def test_customer_order_tracking_route_exists(client):
    paths = client.get("/openapi.json").json()["paths"]
    path = "/api/v1/orders/{order_id}/tracking"
    assert path in paths
    assert "get" in paths[path]


def test_customer_tracking_event_history_route_exists(client):
    paths = client.get("/openapi.json").json()["paths"]
    path = "/api/v1/orders/{order_id}/tracking/shipments/{shipment_id}/events"
    assert path in paths
    assert "get" in paths[path]


def test_customer_tracking_supports_scalable_filters(client):
    operation = client.get("/openapi.json").json()["paths"][
        "/api/v1/orders/{order_id}/tracking"
    ]["get"]
    names = {parameter["name"] for parameter in operation["parameters"]}
    assert {
        "page",
        "page_size",
        "search",
        "status",
        "requires_action",
    }.issubset(names)


def test_customer_tracking_schema_is_multi_seller_aware(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    props = schemas["CustomerShipmentTrackingItem"]["properties"]

    for field in (
        "seller_id",
        "seller_name",
        "logistics_company_name",
        "items",
        "pickup_proof",
        "latest_event",
        "recent_events",
        "requires_customer_action",
    ):
        assert field in props


def test_customer_tracking_summary_exposes_operational_counts(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    props = schemas["CustomerOrderTrackingSummary"]["properties"]

    for field in (
        "shipment_count",
        "pending_count",
        "ready_count",
        "dispatched_count",
        "in_transit_count",
        "out_for_delivery_count",
        "delivered_count",
        "pending_pickup_reviews",
        "disputed_pickup_proofs",
        "requires_customer_action",
    ):
        assert field in props


def test_tracking_progress_contract():
    assert STATUS_PROGRESS["pending"] < STATUS_PROGRESS["ready_for_dispatch"]
    assert STATUS_PROGRESS["ready_for_dispatch"] < STATUS_PROGRESS["dispatched"]
    assert STATUS_PROGRESS["dispatched"] < STATUS_PROGRESS["in_transit"]
    assert STATUS_PROGRESS["in_transit"] < STATUS_PROGRESS["out_for_delivery"]
    assert STATUS_PROGRESS["out_for_delivery"] < STATUS_PROGRESS["delivered"]
    assert STATUS_PROGRESS["delivered"] == 100
    assert STATUS_LABELS["dispatched"] == "Picked up"


def test_existing_phase2_schema_regressions_are_not_removed(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for schema_name in (
        "AddressResponse",
        "EligibleLogisticsSelectionRequest",
        "DeliveryDistanceQuoteRequest",
        "MultiSellerDeliveryPricingRequest",
        "CheckoutDeliveryQuoteResponse",
        "PickupProofResponse",
    ):
        assert schema_name in schemas
