from pathlib import Path
from api.enums import PermissionCode
from api.main import api
from api.models import AdminDashboardSnapshot, SystemAlert, AdminActivityLog

def test_task18_models_and_permissions():
    assert AdminDashboardSnapshot.__tablename__ == "admin_dashboard_snapshots"
    assert SystemAlert.__tablename__ == "system_alerts"
    assert AdminActivityLog.__tablename__ == "admin_activity_logs"
    assert PermissionCode.admin_dashboard_read.value == "admin_dashboard:read"
    assert PermissionCode.admin_system_alerts_manage.value == "admin_system_alerts:manage"

def test_task18_routes_registered():
    paths=api.openapi()["paths"]
    expected=["/api/v1/admin/dashboard/summary","/api/v1/admin/dashboard/sales","/api/v1/admin/dashboard/orders","/api/v1/admin/dashboard/sellers","/api/v1/admin/dashboard/products","/api/v1/admin/dashboard/customers","/api/v1/admin/dashboard/payments","/api/v1/admin/dashboard/refunds","/api/v1/admin/dashboard/delivery","/api/v1/admin/dashboard/notifications","/api/v1/admin/dashboard/search","/api/v1/admin/dashboard/alerts","/api/v1/admin/dashboard/activity-logs"]
    for path in expected: assert path in paths

def test_task18_migration_chain():
    text=Path("alembic/versions/p3_admin_dashboard.py").read_text()
    assert 'revision="p3_admin_dashboard"' in text
    assert 'down_revision="p3_search_recommendations"' in text
