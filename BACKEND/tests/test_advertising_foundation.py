from datetime import datetime, timedelta, timezone

from api.enums import AdvertisementPlacement, AdvertisementStatus
from api.models import Advertisement


def build_ad(*, status=AdvertisementStatus.active, starts_delta=-1, ends_delta=1):
    now = datetime.now(timezone.utc)
    return Advertisement(
        advertiser_name="Test Advertiser",
        title="Test campaign",
        image_url="/uploads/ads/test.webp",
        placement=AdvertisementPlacement.hero_side_top,
        status=status,
        starts_at=now + timedelta(hours=starts_delta),
        ends_at=now + timedelta(hours=ends_delta),
    )


def test_active_ad_is_live_inside_window():
    ad = build_ad()
    assert ad.is_live() is True
    assert ad.effective_status() == "active"


def test_ad_expires_automatically_by_end_datetime():
    ad = build_ad(starts_delta=-2, ends_delta=-1)
    assert ad.is_live() is False
    assert ad.effective_status() == "expired"


def test_future_ad_is_scheduled_not_live():
    ad = build_ad(starts_delta=1, ends_delta=2)
    assert ad.is_live() is False
    assert ad.effective_status() == "scheduled"


def test_paused_ad_is_not_live_inside_time_window():
    ad = build_ad(status=AdvertisementStatus.paused)
    assert ad.is_live() is False
    assert ad.effective_status() == "paused"


def test_advertisement_schedule_constraint_exists():
    constraints = {
        c.name for c in Advertisement.__table__.constraints if c.name
    }
    assert "ck_advertisement_valid_schedule" in constraints
