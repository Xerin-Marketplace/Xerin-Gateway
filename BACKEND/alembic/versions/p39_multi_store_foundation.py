"""Phase 1 multi-store foundation.

Revision ID: p39_multi_store_foundation
Revises: p38_partner_webhooks

Allows one seller to own many stores and records whether each store is local
(Tanzania) or global (outside Tanzania).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p39_multi_store_foundation"
down_revision = "p38_partner_webhooks"
branch_labels = None
depends_on = None


def _seller_unique_constraints(bind):
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints("stores"):
        columns = constraint.get("column_names") or []
        if columns == ["seller_id"] and constraint.get("name"):
            yield constraint["name"]


def upgrade() -> None:
    bind = op.get_bind()

    # Remove the old one-store-per-seller database rule regardless of the
    # generated constraint name in the target PostgreSQL database.
    for constraint_name in _seller_unique_constraints(bind):
        op.drop_constraint(constraint_name, "stores", type_="unique")

    # SQLAlchemy/PostgreSQL enum used by Store.store_scope.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'storescope') THEN
                CREATE TYPE storescope AS ENUM ('local', 'global');
            END IF;
        END
        $$;
        """
    )
    store_scope_enum = postgresql.ENUM(
        "local", "global", name="storescope", create_type=False
    )

    op.add_column(
        "stores",
        sa.Column(
            "store_scope",
            store_scope_enum,
            nullable=True,
            server_default="local",
        ),
    )

    # Existing Tanzanian/unknown legacy stores remain local. Existing stores
    # explicitly located outside Tanzania become global.
    op.execute(
        """
        UPDATE stores
        SET store_scope = CASE
            WHEN country IS NULL OR btrim(country) = '' THEN 'local'::storescope
            WHEN lower(btrim(country)) IN (
                'tanzania',
                'united republic of tanzania',
                'tanzania, united republic of'
            ) THEN 'local'::storescope
            ELSE 'global'::storescope
        END
        """
    )
    op.alter_column("stores", "store_scope", nullable=False)
    op.create_index("ix_stores_store_scope", "stores", ["store_scope"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_stores_store_scope", table_name="stores")
    op.drop_column("stores", "store_scope")
    op.create_unique_constraint("uq_stores_seller_id", "stores", ["seller_id"])
    op.execute("DROP TYPE IF EXISTS storescope")
