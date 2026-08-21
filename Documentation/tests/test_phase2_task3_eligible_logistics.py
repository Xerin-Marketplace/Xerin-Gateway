from types import SimpleNamespace

from api.services.eligible_logistics import (
    LocationFacts,
    _scope_supports,
    _zone_matches_location,
)


def test_zone_match_supports_region_and_city_rules():
    zone = SimpleNamespace(
        is_active=True,
        country="Tanzania",
        regions=["Dar es Salaam"],
        cities=["Kinondoni"],
    )

    assert _zone_matches_location(
        zone,
        LocationFacts(
            country="Tanzania",
            region="Dar es Salaam",
            city="Kinondoni",
        ),
    )
    assert not _zone_matches_location(
        zone,
        LocationFacts(
            country="Tanzania",
            region="Arusha",
            city="Arusha",
        ),
    )


def test_scope_matching():
    assert _scope_supports("local", "local")
    assert _scope_supports("both", "local")
    assert _scope_supports("international", "international")
    assert _scope_supports("both", "international")
    assert not _scope_supports("local", "international")


def test_eligible_logistics_route_exists(client):
    paths = client.get("/openapi.json").json()["paths"]
    path = "/api/v1/shipping/eligible-logistics"
    assert path in paths
    assert "post" in paths[path]


def test_eligible_logistics_route_has_scalable_filters(client):
    operation = client.get("/openapi.json").json()["paths"][
        "/api/v1/shipping/eligible-logistics"
    ]["post"]
    names = {parameter["name"] for parameter in operation["parameters"]}

    assert {
        "page",
        "page_size",
        "search",
        "supports_cod",
        "supports_tracking",
    }.issubset(names)


def test_eligible_logistics_response_schema(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    properties = schemas["PaginatedEligibleLogisticsCompanyResponse"]["properties"]

    for field in (
        "address_id",
        "delivery_mode",
        "seller_count",
        "total",
        "page",
        "page_size",
        "total_pages",
        "sellers",
        "results",
        "excluded_companies",
    ):
        assert field in properties


def test_existing_schema_regressions_are_not_removed(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    for schema_name in (
        "SellerResponse",
        "SellerKYCResponse",
        "SellerPayoutResponse",
        "StoreResponse",
        "UserMeResponse",
        "AddressResponse",
    ):
        assert schema_name in schemas
