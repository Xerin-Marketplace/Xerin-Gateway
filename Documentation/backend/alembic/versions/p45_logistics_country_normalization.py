"""Normalize logistics shipping-zone country names.

Revision ID: p45_logistics_country_normalization
Revises: p44_store_origin_fulfillment
"""
from alembic import op

revision = "p45_logistics_country_normalization"
down_revision = "p44_store_origin_fulfillment"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
        UPDATE shipping_zones
        SET country = CASE lower(trim(country))
            WHEN 'uae' THEN 'United Arab Emirates'
            WHEN 'u.a.e' THEN 'United Arab Emirates'
            WHEN 'emirates' THEN 'United Arab Emirates'
            WHEN 'united arab emirates' THEN 'United Arab Emirates'
            WHEN 'usa' THEN 'United States'
            WHEN 'u.s.a' THEN 'United States'
            WHEN 'us' THEN 'United States'
            WHEN 'united states of america' THEN 'United States'
            WHEN 'uk' THEN 'United Kingdom'
            WHEN 'u.k' THEN 'United Kingdom'
            WHEN 'great britain' THEN 'United Kingdom'
            WHEN 'britain' THEN 'United Kingdom'
            WHEN 'tz' THEN 'Tanzania'
            WHEN 'united republic of tanzania' THEN 'Tanzania'
            WHEN 'tanzania' THEN 'Tanzania'
            WHEN 'prc' THEN 'China'
            WHEN 'people''s republic of china' THEN 'China'
            WHEN 'turkiye' THEN 'Turkey'
            WHEN 'türkiye' THEN 'Turkey'
            ELSE trim(country)
        END
    """)

def downgrade():
    pass
