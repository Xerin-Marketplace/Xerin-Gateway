from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session

from api.enums import CommissionRuleType
from api.services.commission_engine import resolve_commission_rule_for_targets

MONEY = Decimal("0.01")


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def calculate_marketplace_price(
    db: Session,
    *,
    seller_base_price: Decimal,
    seller_id,
    category_id,
    product_id=None,
) -> dict:
    base = money(seller_base_price)
    rule = resolve_commission_rule_for_targets(
        db,
        seller_id=seller_id,
        category_id=category_id,
        product_id=product_id,
    )
    rate = Decimal(rule.rate) if rule else Decimal("0")

    if rule and rule.rule_type == CommissionRuleType.fixed:
        commission = money(rate)
    else:
        commission = money(base * rate / Decimal("100"))

    return {
        "seller_base_price": base,
        "commission_rate": rate,
        "commission_amount": commission,
        "marketplace_price": money(base + commission),
        "commission_rule_id": rule.id if rule else None,
        "commission_scope": rule.scope.value if rule else None,
    }


def apply_product_pricing(db: Session, product, seller_base_price: Decimal, seller_sale_price: Decimal | None = None) -> None:
    normal = calculate_marketplace_price(
        db,
        seller_base_price=seller_base_price,
        seller_id=product.seller_id,
        category_id=product.category_id,
        product_id=product.id,
    )
    product.seller_base_price = normal["seller_base_price"]
    product.commission_rate_snapshot = normal["commission_rate"]
    product.commission_amount_snapshot = normal["commission_amount"]
    product.price = normal["marketplace_price"]

    if seller_sale_price is not None:
        sale = calculate_marketplace_price(
            db,
            seller_base_price=seller_sale_price,
            seller_id=product.seller_id,
            category_id=product.category_id,
            product_id=product.id,
        )
        product.seller_sale_price = sale["seller_base_price"]
        product.sale_price = sale["marketplace_price"]
    else:
        product.seller_sale_price = None
        product.sale_price = None


def apply_variant_pricing(db: Session, variant, product, seller_base_price: Decimal | None, seller_sale_price: Decimal | None = None) -> None:
    if seller_base_price is None:
        variant.seller_base_price = None
        variant.seller_sale_price = None
        variant.commission_rate_snapshot = None
        variant.commission_amount_snapshot = None
        variant.price = None
        variant.sale_price = None
        return

    normal = calculate_marketplace_price(
        db,
        seller_base_price=seller_base_price,
        seller_id=product.seller_id,
        category_id=product.category_id,
        product_id=product.id,
    )
    variant.seller_base_price = normal["seller_base_price"]
    variant.commission_rate_snapshot = normal["commission_rate"]
    variant.commission_amount_snapshot = normal["commission_amount"]
    variant.price = normal["marketplace_price"]

    if seller_sale_price is not None:
        sale = calculate_marketplace_price(
            db,
            seller_base_price=seller_sale_price,
            seller_id=product.seller_id,
            category_id=product.category_id,
            product_id=product.id,
        )
        variant.seller_sale_price = sale["seller_base_price"]
        variant.sale_price = sale["marketplace_price"]
    else:
        variant.seller_sale_price = None
        variant.sale_price = None
