from api.enums import ShipmentStatus
from api.models import Order, Shipment, ShipmentItem, ShipmentTrackingEvent
from api.routers.shipping import ALLOWED_SHIPMENT_TRANSITIONS
from api.schemas import OrderCreateRequest


def test_checkout_requires_server_shipping_rate():
    fields = OrderCreateRequest.model_fields
    assert fields["shipping_address_id"].is_required()
    assert fields["shipping_rate_id"].is_required()


def test_order_stores_shipping_snapshot():
    for name in ("shipping_rate_id", "shipping_method_id", "shipping_method_name", "shipping_carrier", "estimated_delivery_from", "estimated_delivery_to"):
        assert hasattr(Order, name)


def test_shipment_models_exist():
    assert Shipment.__tablename__ == "shipments"
    assert ShipmentItem.__tablename__ == "shipment_items"
    assert ShipmentTrackingEvent.__tablename__ == "shipment_tracking_events"


def test_unsafe_shipment_transition_rejected_by_contract():
    assert ShipmentStatus.delivered not in ALLOWED_SHIPMENT_TRANSITIONS[ShipmentStatus.pending]
    assert not ALLOWED_SHIPMENT_TRANSITIONS[ShipmentStatus.delivered]
    assert ShipmentStatus.dispatched in ALLOWED_SHIPMENT_TRANSITIONS[ShipmentStatus.ready_for_dispatch]
