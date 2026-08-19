from pathlib import Path
from api.models import LogisticsIntegrationConfig

def test_integration_model_contract():
    assert hasattr(LogisticsIntegrationConfig, "webhook_enabled_events")
    assert hasattr(LogisticsIntegrationConfig, "last_webhook_sent_at")
    assert hasattr(LogisticsIntegrationConfig, "last_webhook_received_at")

def test_task6_routes_registered(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/api/v1/logistics/me/integration"]
    assert "put" in paths["/api/v1/logistics/me/integration"]
    assert "get" in paths["/api/v1/logistics/me/webhook-events"]
    assert "get" in paths["/api/v1/logistics/me/dashboard"]

def test_task6_migration_extends_task5():
    migration = Path("alembic/versions/p29_logistics_integration_dashboard.py").read_text()
    assert 'revision = "p29_logistics_integration_dashboard"' in migration
    assert 'down_revision = "p28_logistics_pickup_tracking"' in migration
