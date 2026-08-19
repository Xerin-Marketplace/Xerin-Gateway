from pathlib import Path

import pytest
from pydantic import ValidationError

from api.models import LogisticsCompany, ShippingZone
from api.schemas import ShippingZoneCreate
from api.services.eligible_logistics import LocationFacts, _zone_matches_location


def test_zone_model_is_company_owned():
    assert hasattr(ShippingZone, "logistics_company_id")
    assert hasattr(ShippingZone, "logistics_company")
    assert hasattr(LogisticsCompany, "zones")


def test_zone_model_has_granular_coverage_fields():
    for field in (
        "districts",
        "wards",
        "postal_codes",
        "coverage_geojson",
        "covers_entire_country",
    ):
        assert hasattr(ShippingZone, field)


def test_zone_requires_coverage_or_countrywide_flag():
    with pytest.raises(ValidationError):
        ShippingZoneCreate(name="Empty Zone")
    zone = ShippingZoneCreate(name="Tanzania", covers_entire_country=True)
    assert zone.covers_entire_country is True


def test_zone_normalises_and_deduplicates_places():
    zone = ShippingZoneCreate(
        name="Dar es Salaam",
        regions=[" Dar es Salaam ", "dar es salaam"],
        districts=["Kinondoni", " kinondoni "],
    )
    assert zone.regions == ["Dar es Salaam"]
    assert zone.districts == ["Kinondoni"]


def test_zone_rejects_unsupported_geojson_type():
    with pytest.raises(ValidationError):
        ShippingZoneCreate(
            name="Invalid Geometry",
            coverage_geojson={"type": "Point", "coordinates": [39.2, -6.8]},
        )


def test_zone_coverage_matches_granular_location():
    zone = ShippingZone(
        name="Kinondoni",
        country="Tanzania",
        regions=["Dar es Salaam"],
        cities=[],
        districts=["Kinondoni"],
        wards=["Mikocheni"],
        postal_codes=[],
        coverage_geojson=None,
        covers_entire_country=False,
        is_active=True,
    )
    assert _zone_matches_location(
        zone,
        LocationFacts(
            country="Tanzania",
            region="Dar es Salaam",
            city="Dar es Salaam",
            district="Kinondoni",
            ward="Mikocheni",
        ),
    )
    assert not _zone_matches_location(
        zone,
        LocationFacts(
            country="Tanzania",
            region="Dar es Salaam",
            city="Dar es Salaam",
            district="Ilala",
            ward="Upanga",
        ),
    )


def test_zone_geojson_polygon_matches_coordinates():
    zone = ShippingZone(
        name="Dar Polygon",
        country="Tanzania",
        regions=[],
        cities=[],
        districts=[],
        wards=[],
        postal_codes=[],
        coverage_geojson={
            "type": "Polygon",
            "coordinates": [[[39.0, -7.0], [40.0, -7.0], [40.0, -6.0], [39.0, -6.0], [39.0, -7.0]]],
        },
        covers_entire_country=False,
        is_active=True,
    )
    assert _zone_matches_location(
        zone,
        LocationFacts(
            country="Tanzania",
            region="Dar es Salaam",
            city="Dar es Salaam",
            latitude=-6.8,
            longitude=39.2,
        ),
    )


def test_company_zone_routes_registered(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/api/v1/logistics/me/zones"]
    assert "post" in paths["/api/v1/logistics/me/zones"]
    assert "get" in paths["/api/v1/logistics/me/zones/{zone_id}"]
    assert "patch" in paths["/api/v1/logistics/me/zones/{zone_id}"]
    assert "delete" in paths["/api/v1/logistics/me/zones/{zone_id}"]


def test_task3_migration_extends_task2():
    migration = Path("alembic/versions/p26_logistics_delivery_zones.py").read_text()
    assert 'revision = "p26_logistics_delivery_zones"' in migration
    assert 'down_revision = "p25_logistics_company_users"' in migration
