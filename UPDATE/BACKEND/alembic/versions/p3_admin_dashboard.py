"""Phase 3 Task 18: marketplace administration dashboard.
Revision ID: p3_admin_dashboard
Revises: p3_search_recommendations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="p3_admin_dashboard"; down_revision="p3_search_recommendations"; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("admin_dashboard_snapshots",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("period_start",sa.DateTime(timezone=True),nullable=False),sa.Column("period_end",sa.DateTime(timezone=True),nullable=False),sa.Column("metrics",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("generated_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("generated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.CheckConstraint("period_end >= period_start",name="ck_admin_dashboard_snapshot_period")); op.create_index("ix_admin_dashboard_snapshots_period_start","admin_dashboard_snapshots",["period_start"]); op.create_index("ix_admin_dashboard_snapshots_period_end","admin_dashboard_snapshots",["period_end"])
    op.create_table("system_alerts",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("alert_type",sa.String(80),nullable=False),sa.Column("severity",sa.String(20),nullable=False,server_default="warning"),sa.Column("title",sa.String(255),nullable=False),sa.Column("message",sa.Text(),nullable=False),sa.Column("source",sa.String(100)),sa.Column("entity_type",sa.String(80)),sa.Column("entity_id",sa.String(100)),sa.Column("metadata_json",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("is_resolved",sa.Boolean(),nullable=False,server_default=sa.false()),sa.Column("resolved_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("resolved_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.CheckConstraint("severity IN ('info','warning','error','critical')",name="ck_system_alert_severity"));
    for c in ("alert_type","severity","source","is_resolved","created_at"): op.create_index(f"ix_system_alerts_{c}","system_alerts",[c])
    op.create_table("admin_activity_logs",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("admin_user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("action",sa.String(120),nullable=False),sa.Column("resource_type",sa.String(100)),sa.Column("resource_id",sa.String(100)),sa.Column("details",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("ip_address",sa.String(64)),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for c in ("admin_user_id","action","resource_type","created_at"): op.create_index(f"ix_admin_activity_logs_{c}","admin_activity_logs",[c])

def downgrade():
    op.drop_table("admin_activity_logs"); op.drop_table("system_alerts"); op.drop_table("admin_dashboard_snapshots")
