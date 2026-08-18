from datetime import datetime, timedelta, timezone

from api.enums import AdvertisementPlacement, AdvertisementStatus, PermissionCode
from api.schemas import AdvertisementCreate, AdvertisementUpdate


def test_advertisement_permissions_exist():
    assert PermissionCode.advertisements_read.value == "advertisements:read"
    assert PermissionCode.advertisements_manage.value == "advertisements:manage"


def test_ad_create_requires_timezone_aware_window():
    now = datetime.now(timezone.utc)
    data = AdvertisementCreate(
        advertiser_name="Xerin Partner",
        title="Weekend Campaign",
        image_url="/uploads/advertisements/banner.webp",
        placement=AdvertisementPlacement.hero_side_top,
        starts_at=now,
        ends_at=now + timedelta(days=2),
    )
    assert data.ends_at > data.starts_at


def test_ad_create_rejects_invalid_window():
    now = datetime.now(timezone.utc)
    try:
        AdvertisementCreate(
            advertiser_name="Xerin Partner",
            title="Broken Campaign",
            image_url="/uploads/advertisements/banner.webp",
            placement=AdvertisementPlacement.hero_side_top,
            starts_at=now,
            ends_at=now - timedelta(seconds=1),
        )
    except Exception:
        return
    raise AssertionError("Invalid advertisement window should fail validation")


def test_ad_update_supports_scheduling_and_pause():
    now = datetime.now(timezone.utc)
    data = AdvertisementUpdate(
        status=AdvertisementStatus.active,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(days=1),
    )
    assert data.status == AdvertisementStatus.active


def test_admin_advertisement_paths_are_in_openapi(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]

    root = "/api/v1/admin/advertisements"
    detail = "/api/v1/admin/advertisements/{advertisement_id}"
    activate = "/api/v1/admin/advertisements/{advertisement_id}/activate"
    pause = "/api/v1/admin/advertisements/{advertisement_id}/pause"

    assert "get" in paths[root]
    assert "post" in paths[root]
    assert "get" in paths[detail]
    assert "patch" in paths[detail]
    assert "delete" in paths[detail]
    assert "post" in paths[activate]
    assert "post" in paths[pause]
