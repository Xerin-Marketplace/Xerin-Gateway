"""Phase 3 Task 17: search and recommendations.

Revision ID: p3_search_recommendations
Revises: p3_product_qa
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_search_recommendations"
down_revision = "p3_product_qa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("search_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("query", sa.String(255), nullable=False), sa.Column("normalized_query", sa.String(255), nullable=False),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("result_count >= 0", name="ck_search_history_result_count"))
    op.create_index("ix_search_history_user_id", "search_history", ["user_id"]); op.create_index("ix_search_history_normalized_query", "search_history", ["normalized_query"]); op.create_index("ix_search_history_user_created", "search_history", ["user_id", "created_at"]); op.create_index("ix_search_history_query_created", "search_history", ["normalized_query", "created_at"])
    op.create_table("search_terms", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("term", sa.String(255), nullable=False), sa.Column("search_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("result_click_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_searched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.CheckConstraint("search_count >= 0", name="ck_search_term_search_count"), sa.CheckConstraint("result_click_count >= 0", name="ck_search_term_click_count"), sa.UniqueConstraint("term", name="uq_search_terms_term")); op.create_index("ix_search_terms_term", "search_terms", ["term"], unique=True)
    op.create_table("product_views", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("session_id", sa.String(128)), sa.Column("source", sa.String(64)), sa.Column("search_query", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())); op.create_index("ix_product_views_product_id", "product_views", ["product_id"]); op.create_index("ix_product_views_user_id", "product_views", ["user_id"]); op.create_index("ix_product_views_session_id", "product_views", ["session_id"]); op.create_index("ix_product_views_product_created", "product_views", ["product_id", "created_at"])
    op.create_table("product_recommendations", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False), sa.Column("recommendation_type", sa.String(64), nullable=False, server_default="personalized"), sa.Column("score", sa.Float(), nullable=False, server_default="0"), sa.Column("reason", sa.String(255)), sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("expires_at", sa.DateTime(timezone=True)), sa.CheckConstraint("score >= 0", name="ck_product_recommendation_score"), sa.UniqueConstraint("user_id", "product_id", "recommendation_type", name="uq_product_recommendation_user_product_type")); op.create_index("ix_product_recommendations_user_id", "product_recommendations", ["user_id"]); op.create_index("ix_product_recommendations_product_id", "product_recommendations", ["product_id"])
    op.create_table("recommendation_events", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False), sa.Column("event_type", sa.String(64), nullable=False), sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.CheckConstraint("char_length(event_type) >= 2", name="ck_recommendation_event_type")); op.create_index("ix_recommendation_events_user_id", "recommendation_events", ["user_id"]); op.create_index("ix_recommendation_events_product_id", "recommendation_events", ["product_id"]); op.create_index("ix_recommendation_events_event_type", "recommendation_events", ["event_type"])


def downgrade():
    for table in ("recommendation_events", "product_recommendations", "product_views", "search_terms", "search_history"):
        op.drop_table(table)
