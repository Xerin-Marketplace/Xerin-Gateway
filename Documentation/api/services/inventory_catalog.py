from __future__ import annotations

from sqlalchemy.orm import Session

from api.models import Inventory, Product, ProductVariant


def inventory_configuration_errors(
    db: Session,
    product: Product,
) -> list[str]:
    """Return catalogue-readiness errors for a product's stock configuration.

    A non-variant product requires exactly the base inventory row
    (`variant_id IS NULL`). A product with active variants requires one
    inventory row for every active variant.

    Zero stock is valid configuration: it simply means OUT OF STOCK. The
    distinction here is between configured stock (including zero) and missing
    stock configuration.
    """

    active_variants = (
        db.query(ProductVariant)
        .filter(
            ProductVariant.product_id == product.id,
            ProductVariant.is_active.is_(True),
        )
        .all()
    )

    if active_variants:
        variant_ids = {variant.id for variant in active_variants}
        configured_variant_ids = {
            row.variant_id
            for row in (
                db.query(Inventory.variant_id)
                .filter(
                    Inventory.product_id == product.id,
                    Inventory.variant_id.in_(variant_ids),
                )
                .all()
            )
        }

        missing = [
            variant
            for variant in active_variants
            if variant.id not in configured_variant_ids
        ]
        if not missing:
            return []

        labels = ", ".join(
            variant.sku or variant.variant_name or str(variant.id)
            for variant in missing[:10]
        )
        more = len(missing) - 10
        if more > 0:
            labels += f", and {more} more"

        return [
            (
                "Configure inventory for every active product variant before "
                f"marketplace review. Missing: {labels}"
            )
        ]

    base_inventory = (
        db.query(Inventory.id)
        .filter(
            Inventory.product_id == product.id,
            Inventory.variant_id.is_(None),
        )
        .first()
    )

    if base_inventory is None:
        return [
            (
                "Configure opening inventory for this product before "
                "marketplace review. A stock quantity of 0 is allowed."
            )
        ]

    return []
