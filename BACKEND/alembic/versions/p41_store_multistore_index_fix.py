"""Phase 3.1: repair legacy unique stores.seller_id indexes.

Revision ID: p41_store_multistore_index_fix
Revises: p40_product_store_assignment

Some older databases created ``ix_stores_seller_id`` as a UNIQUE index because
Store.seller_id originally had ``unique=True, index=True``.  Phase 1 removed
unique constraints, but a PostgreSQL unique index can exist independently and
therefore continue enforcing one store per seller.  This migration removes any
single-column UNIQUE index/constraint on seller_id and leaves a normal lookup
index in its place.
"""

from alembic import op
import sqlalchemy as sa

revision = "p41_store_multistore_index_fix"
down_revision = "p40_product_store_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop named UNIQUE constraints on exactly stores.seller_id.
    for constraint in inspector.get_unique_constraints("stores"):
        columns = constraint.get("column_names") or []
        name = constraint.get("name")
        if columns == ["seller_id"] and name:
            op.drop_constraint(name, "stores", type_="unique")

    # Refresh inspection after constraint changes and remove any remaining
    # standalone UNIQUE indexes on exactly stores.seller_id.
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("stores"):
        columns = index.get("column_names") or []
        name = index.get("name")
        if columns == ["seller_id"] and index.get("unique") and name:
            op.drop_index(name, table_name="stores")

    # Guarantee the intended non-unique lookup index exists.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stores_seller_id ON stores (seller_id)"
    )


def downgrade() -> None:
    # Downgrade is intentionally conservative: restoring uniqueness can fail on
    # legitimate multi-store data created after this migration.  Remove only the
    # normal index; do not destroy or invalidate multi-store records.
    op.execute("DROP INDEX IF EXISTS ix_stores_seller_id")
