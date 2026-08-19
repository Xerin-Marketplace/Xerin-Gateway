from pathlib import Path

from api.enums import PickupJobStatus
from api.models import LogisticsPickupJob
from api.routers.logistics import PICKUP_JOB_TRANSITIONS


def test_pickup_job_model_contract():
    assert LogisticsPickupJob.__tablename__ == "logistics_pickup_jobs"
    for field in ("shipment_id", "assigned_membership_id", "pickup_reference", "status", "completed_at"):
        assert hasattr(LogisticsPickupJob, field)


def test_pickup_status_transitions():
    assert PickupJobStatus.assigned in PICKUP_JOB_TRANSITIONS[PickupJobStatus.scheduled]
    assert PickupJobStatus.en_route in PICKUP_JOB_TRANSITIONS[PickupJobStatus.assigned]
    assert PickupJobStatus.arrived in PICKUP_JOB_TRANSITIONS[PickupJobStatus.en_route]
    assert PickupJobStatus.completed in PICKUP_JOB_TRANSITIONS[PickupJobStatus.arrived]
    assert PickupJobStatus.completed not in PICKUP_JOB_TRANSITIONS[PickupJobStatus.scheduled]


def test_pickup_job_routes_registered(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/api/v1/logistics/me/pickup-jobs"]
    assert "post" in paths["/api/v1/logistics/me/shipments/{shipment_id}/pickup-job"]
    assert "patch" in paths["/api/v1/logistics/me/pickup-jobs/{job_id}/assign"]
    assert "post" in paths["/api/v1/logistics/me/pickup-jobs/{job_id}/status"]


def test_task5_migration_extends_task4():
    migration = Path("alembic/versions/p28_logistics_pickup_tracking.py").read_text()
    assert 'revision = "p28_logistics_pickup_tracking"' in migration
    assert 'down_revision = "p27_logistics_pricing"' in migration
