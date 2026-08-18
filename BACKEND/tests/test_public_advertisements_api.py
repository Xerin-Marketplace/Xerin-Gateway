from datetime import datetime, timedelta, timezone

from api.enums import AdvertisementPlacement, AdvertisementStatus
from api.models import Advertisement


def _ad(*, starts_at, ends_at, status=AdvertisementStatus.active):
    return Advertisement(
        advertiser_name="Test Brand",
        title="Test Sponsored Campaign",
        image_url="/uploads/advertisements/test.webp",
        placement=AdvertisementPlacement.hero_side_top,
        status=status,
        starts_at=starts_at,
        ends_at=ends_at,
    )


def test_public_advertisement_paths_exist(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    assert "/api/v1/advertisements/active" in paths
    assert "/api/v1/advertisements/slots" in paths
    assert "/api/v1/advertisements/slot/{placement}" in paths


def test_public_routes_do_not_require_authentication_in_openapi(client):
    response = client.get("/openapi.json")
    paths = response.json()["paths"]

    for path in (
        "/api/v1/advertisements/active",
        "/api/v1/advertisements/slots",
        "/api/v1/advertisements/slot/{placement}",
    ):
        operation = paths[path]["get"]
        # The route itself should not define an auth dependency/security scheme.
        assert not operation.get("security")


def test_exact_end_time_is_not_live():
    now = datetime.now(timezone.utc)
    ad = _ad(
        starts_at=now - timedelta(hours=1),
        ends_at=now,
    )
    assert ad.is_live(at=now) is False
    assert ad.effective_status(at=now) == "expired"


def test_campaign_is_live_before_end_time():
    now = datetime.now(timezone.utc)
    ad = _ad(
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(microseconds=1),
    )
    assert ad.is_live(at=now) is True


def test_future_campaign_is_not_live():
    now = datetime.now(timezone.utc)
    ad = _ad(
        starts_at=now + timedelta(minutes=1),
        ends_at=now + timedelta(hours=1),
    )
    assert ad.is_live(at=now) is False
    assert ad.effective_status(at=now) == "scheduled"


def test_paused_campaign_is_not_live_even_inside_window():
    now = datetime.now(timezone.utc)
    ad = _ad(
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        status=AdvertisementStatus.paused,
    )
    assert ad.is_live(at=now) is False
