"""Add permission-driven support ticket workflow.

Revision ID: p5_support_tickets
Revises: p4_catalog_search_indexes
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p5_support_tickets"
down_revision = "p4_catalog_search_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_reviews", sa.Column("admin_reply", sa.Text(), nullable=True))
    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_number", sa.String(length=40), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("channel", sa.String(length=50), server_default="customer", nullable=False),
        sa.Column("priority", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("priority IN ('low','medium','high','urgent')", name="ck_support_ticket_priority"),
        sa.CheckConstraint("status IN ('open','pending','in_progress','processing','resolved','closed')", name="ck_support_ticket_status"),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_number"),
    )
    for name, cols, unique in [
        ("ix_support_tickets_ticket_number", ["ticket_number"], True),
        ("ix_support_tickets_customer_id", ["customer_id"], False),
        ("ix_support_tickets_seller_id", ["seller_id"], False),
        ("ix_support_tickets_order_id", ["order_id"], False),
        ("ix_support_tickets_shipment_id", ["shipment_id"], False),
        ("ix_support_tickets_assigned_to_id", ["assigned_to_id"], False),
        ("ix_support_tickets_status", ["status"], False),
        ("ix_support_tickets_priority", ["priority"], False),
        ("ix_support_tickets_channel", ["channel"], False),
        ("ix_support_tickets_category", ["category"], False),
        ("ix_support_tickets_created_at", ["created_at"], False),
        ("ix_support_tickets_status_priority_created", ["status","priority","created_at"], False),
    ]:
        op.create_index(name, "support_tickets", cols, unique=unique)

    op.create_table(
        "support_ticket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sender_role", sa.String(length=50), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=20), server_default="all", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('all','internal')", name="ck_support_ticket_message_visibility"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_ticket_messages_ticket_id", "support_ticket_messages", ["ticket_id"])
    op.create_index("ix_support_ticket_messages_sender_id", "support_ticket_messages", ["sender_id"])
    op.create_index("ix_support_ticket_messages_created_at", "support_ticket_messages", ["created_at"])

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_support_tickets_ticket_number_trgm ON support_tickets USING gin (ticket_number gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_support_tickets_subject_trgm ON support_tickets USING gin (subject gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_support_tickets_description_trgm ON support_tickets USING gin (description gin_trgm_ops)")


def downgrade() -> None:
    op.drop_column("product_reviews", "admin_reply")
    op.execute("DROP INDEX IF EXISTS ix_support_tickets_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_support_tickets_subject_trgm")
    op.execute("DROP INDEX IF EXISTS ix_support_tickets_ticket_number_trgm")
    op.drop_table("support_ticket_messages")
    op.drop_table("support_tickets")
