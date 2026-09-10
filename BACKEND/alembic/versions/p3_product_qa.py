"""Phase 3 Task 16: product questions and answers.

Revision ID: p3_product_qa
Revises: p3_notifications
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_product_qa"
down_revision = "p3_notifications"
branch_labels = None
depends_on = None

question_status = postgresql.ENUM("pending", "published", "hidden", "rejected", name="questionstatus", create_type=False)
report_reason = postgresql.ENUM("spam", "abusive", "misleading", "inappropriate", "other", name="questionreportreason", create_type=False)


def upgrade():
    bind = op.get_bind()
    question_status.create(bind, checkfirst=True)
    report_reason.create(bind, checkfirst=True)
    op.create_table(
        "product_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", question_status, nullable=False, server_default="published"),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("moderated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("moderated_at", sa.DateTime(timezone=True)),
        sa.Column("moderation_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(question) >= 5", name="ck_product_question_min_length"),
        sa.CheckConstraint("helpful_count >= 0", name="ck_product_question_helpful_count"),
        sa.CheckConstraint("answer_count >= 0", name="ck_product_question_answer_count"),
    )
    for col in ("product_id", "customer_id", "status"):
        op.create_index(f"ix_product_questions_{col}", "product_questions", [col])
    op.create_table(
        "product_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_seller_answer", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_official", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", question_status, nullable=False, server_default="published"),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("char_length(answer) >= 2", name="ck_product_answer_min_length"),
        sa.CheckConstraint("helpful_count >= 0", name="ck_product_answer_helpful_count"),
    )
    for col in ("question_id", "user_id", "status"):
        op.create_index(f"ix_product_answers_{col}", "product_answers", [col])
    op.create_table("question_votes", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_questions.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("question_id", "user_id", name="uq_question_vote_question_user"))
    op.create_index("ix_question_votes_question_id", "question_votes", ["question_id"]); op.create_index("ix_question_votes_user_id", "question_votes", ["user_id"])
    op.create_table("answer_votes", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("answer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_answers.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("answer_id", "user_id", name="uq_answer_vote_answer_user"))
    op.create_index("ix_answer_votes_answer_id", "answer_votes", ["answer_id"]); op.create_index("ix_answer_votes_user_id", "answer_votes", ["user_id"])
    op.create_table("question_reports", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_questions.id", ondelete="CASCADE"), nullable=False), sa.Column("reported_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("reason", report_reason, nullable=False), sa.Column("details", sa.Text()), sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("question_id", "reported_by_id", name="uq_question_report_question_user"))
    op.create_index("ix_question_reports_question_id", "question_reports", ["question_id"]); op.create_index("ix_question_reports_reported_by_id", "question_reports", ["reported_by_id"])


def downgrade():
    for table in ("question_reports", "answer_votes", "question_votes", "product_answers", "product_questions"):
        op.drop_table(table)
    bind = op.get_bind()
    report_reason.drop(bind, checkfirst=True)
    question_status.drop(bind, checkfirst=True)
