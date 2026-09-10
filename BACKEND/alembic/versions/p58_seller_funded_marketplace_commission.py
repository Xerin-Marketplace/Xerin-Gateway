"""seller funded marketplace commission pricing

Revision ID: p58_seller_funded_marketplace_commission
Revises: p57_staff_device_session_security

Customer-facing product prices now equal seller-entered listing prices.
Historical order/order-item/commission snapshots are intentionally untouched.
"""

from alembic import op

revision = "p58_seller_funded_marketplace_commission"
down_revision = "p57_staff_device_session_security"
branch_labels = None
depends_on = None


def upgrade():
    # Products created under the previous pricing model stored customer price as
    # seller_base_price + marketplace commission. Reset only current catalogue
    # prices; historical orders preserve their immutable snapshots.
    op.execute(
        """
        UPDATE products
        SET price = seller_base_price,
            sale_price = seller_sale_price,
            commission_amount_snapshot = LEAST(
                COALESCE(commission_amount_snapshot, 0),
                seller_base_price
            )
        WHERE seller_base_price IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE product_variants
        SET price = seller_base_price,
            sale_price = seller_sale_price,
            commission_amount_snapshot = LEAST(
                COALESCE(commission_amount_snapshot, 0),
                seller_base_price
            )
        WHERE seller_base_price IS NOT NULL
        """
    )


def downgrade():
    # Previous customer prices cannot be reconstructed safely from snapshots
    # because commission rules may have changed since a listing was created.
    # Keep the corrected catalogue prices rather than invent historical values.
    pass
