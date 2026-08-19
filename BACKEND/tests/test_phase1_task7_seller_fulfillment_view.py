def test_seller_fulfillment_routes_exist(client):
    paths = client.get("/openapi.json").json()["paths"]

    expected = (
        "/api/v1/seller/fulfillment/summary",
        "/api/v1/seller/fulfillment",
        "/api/v1/seller/fulfillment/{seller_order_id}",
        "/api/v1/seller/fulfillment/{seller_order_id}/tracking",
    )

    for path in expected:
        assert path in paths


def test_fulfillment_list_has_pagination_parameters(client):
    operation = client.get("/openapi.json").json()["paths"][
        "/api/v1/seller/fulfillment"
    ]["get"]

    names = {parameter["name"] for parameter in operation["parameters"]}
    assert {"page", "page_size", "search"}.issubset(names)
    assert {"seller_status", "shipment_status", "handover_status"}.issubset(names)


def test_tracking_endpoint_has_pagination(client):
    operation = client.get("/openapi.json").json()["paths"][
        "/api/v1/seller/fulfillment/{seller_order_id}/tracking"
    ]["get"]

    names = {parameter["name"] for parameter in operation["parameters"]}
    assert {"page", "page_size"}.issubset(names)
