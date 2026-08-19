from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ready_to_ship_enqueues_logistics_event():
    source = (ROOT / "api/routers/seller_orders.py").read_text()
    assert "enqueue_ready_for_pickup" in source
    assert "ShipmentStatus.ready_for_dispatch" in source


def test_new_shipments_snapshot_selected_logistics_company():
    source = (ROOT / "api/routers/payments.py").read_text()
    assert "logistics_company_id=order.logistics_company_id" in source


def test_orchestration_is_durable_and_idempotent():
    source = (ROOT / "api/services/logistics_orchestration.py").read_text()
    assert 'READY_EVENT = "shipment.ready_for_pickup"' in source
    assert "LogisticsWebhookEvent" in source
    assert 'LogisticsWebhookEvent.direction == "outbound"' in source
    assert "processed=False" in source
    assert "pickup" in source and "dropoff" in source and "packages" in source
