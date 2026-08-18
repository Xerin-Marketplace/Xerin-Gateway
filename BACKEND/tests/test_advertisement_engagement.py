from datetime import datetime, timedelta, timezone

from api.models import AdvertisementEngagementEvent


def test_engagement_table_has_unique_event_key():
    indexes = {
        index.name: index.unique
        for index in AdvertisementEngagementEvent.__table__.indexes
    }
    assert indexes["ix_advertisement_engagement_events_event_key"] is True


def test_ad_tracking_routes_exist(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    impression = "/api/v1/advertisements/{advertisement_id}/impression"
    click = "/api/v1/advertisements/{advertisement_id}/click"

    assert impression in paths
    assert click in paths
    assert "post" in paths[impression]
    assert "post" in paths[click]


def test_tracking_routes_are_public(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/api/v1/advertisements/{advertisement_id}/impression",
        "/api/v1/advertisements/{advertisement_id}/click",
    ):
        assert not paths[path]["post"].get("security")
