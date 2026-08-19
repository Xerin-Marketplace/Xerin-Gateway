from api.models import ShipmentHandover


def test_handover_model_has_one_record_per_shipment_and_seller_order():
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in ShipmentHandover.__table__.constraints
        if getattr(constraint, "unique", False) or constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("shipment_id",) in unique_columns
    assert ("seller_order_id",) in unique_columns


def test_handover_routes_exist(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/seller/orders/{seller_order_id}/handover" in paths
    assert "/api/v1/seller/orders/{seller_order_id}/handover/confirm" in paths
    assert "/api/v1/logistics/me/shipments/{shipment_id}/handover" in paths
    assert "/api/v1/logistics/me/shipments/{shipment_id}/arrived-for-pickup" in paths


def test_handover_is_not_generic_crud_resource(client):
    paths = client.get("/openapi.json").json()["paths"]
    seller_path = paths["/api/v1/seller/orders/{seller_order_id}/handover"]
    assert "delete" not in seller_path
    assert "patch" not in seller_path
