from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.models import Inventory, Product, ProductSpecification, ProductStatus

DEFAULT_SIMILARITY_THRESHOLD = Decimal("75")


def _has_value(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _as_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _multiselect_similarity(left: Any, right: Any) -> Decimal:
    if not isinstance(left, list) or not isinstance(right, list):
        return Decimal("0")
    a = {str(item).strip().casefold() for item in left if str(item).strip()}
    b = {str(item).strip().casefold() for item in right if str(item).strip()}
    if not a or not b:
        return Decimal("0")
    return Decimal(len(a & b)) / Decimal(len(a | b))


def _number_similarity(left: Any, right: Any) -> Decimal:
    a = _as_decimal(left)
    b = _as_decimal(right)
    if a is None or b is None:
        return Decimal("0")
    if a == b:
        return Decimal("1")
    denominator = max(abs(a), abs(b), Decimal("1"))
    relative_difference = abs(a - b) / denominator
    if relative_difference <= Decimal("0.05"):
        return Decimal("0.80")
    if relative_difference <= Decimal("0.10"):
        return Decimal("0.50")
    return Decimal("0")


def _value_similarity(source: ProductSpecification, candidate: ProductSpecification) -> Decimal:
    input_type = source.attribute.input_type
    if input_type == "multiselect":
        return _multiselect_similarity(source.value, candidate.value)
    if input_type == "number":
        return _number_similarity(source.value, candidate.value)
    if source.normalized_value is None or candidate.normalized_value is None:
        return Decimal("0")
    return Decimal("1") if source.normalized_value == candidate.normalized_value else Decimal("0")


def similar_product_matches(
    db: Session,
    source: Product,
    *,
    threshold: Decimal = DEFAULT_SIMILARITY_THRESHOLD,
    limit: int = 8,
) -> list[dict]:
    source_rows = (
        db.query(ProductSpecification)
        .options(selectinload(ProductSpecification.attribute))
        .filter(ProductSpecification.product_id == source.id)
        .all()
    )
    source_specs = {
        row.attribute.key: row
        for row in source_rows
        if row.attribute.is_active
        and row.attribute.use_for_similarity
        and _has_value(row.value)
        and Decimal(str(row.attribute.similarity_weight or 0)) > 0
    }
    if not source_specs:
        return []

    query = (
        db.query(Product)
        .options(selectinload(Product.images))
        .filter(
            Product.id != source.id,
            Product.category_id == source.category_id,
            Product.status == ProductStatus.approved,
            Product.is_active.is_(True),
        )
    )

    # "Similar offers" should favor another marketplace seller/listing owner,
    # not another SKU from the exact same seller account.
    if source.seller_id is not None:
        query = query.filter(
            Product.listing_owner_type == "seller",
            Product.seller_id.is_not(None),
            Product.seller_id != source.seller_id,
        )
    elif source.broker_id is not None:
        query = query.filter((Product.broker_id.is_(None)) | (Product.broker_id != source.broker_id))

    candidates = query.limit(200).all()
    if not candidates:
        return []

    candidate_ids = [item.id for item in candidates]
    rows = (
        db.query(ProductSpecification)
        .options(selectinload(ProductSpecification.attribute))
        .filter(ProductSpecification.product_id.in_(candidate_ids))
        .all()
    )
    by_product: dict[UUID, dict[str, ProductSpecification]] = {}
    for row in rows:
        if not row.attribute.is_active or not row.attribute.use_for_similarity or not _has_value(row.value):
            continue
        by_product.setdefault(row.product_id, {})[row.attribute.key] = row

    stock_rows = (
        db.query(Inventory.product_id, func.coalesce(func.sum(Inventory.available_quantity), 0))
        .filter(Inventory.product_id.in_(candidate_ids))
        .group_by(Inventory.product_id)
        .all()
    )
    stock_by_product = {product_id: int(quantity or 0) for product_id, quantity in stock_rows}

    matches: list[dict] = []
    for candidate in candidates:
        candidate_specs = by_product.get(candidate.id, {})
        weighted_total = Decimal("0")
        possible_total = Decimal("0")
        matched_attributes: list[dict] = []

        for key, source_spec in source_specs.items():
            weight = Decimal(str(source_spec.attribute.similarity_weight or 0))
            if weight <= 0:
                continue
            possible_total += weight
            candidate_spec = candidate_specs.get(key)
            if candidate_spec is None:
                continue
            similarity = _value_similarity(source_spec, candidate_spec)
            weighted_total += weight * similarity
            if similarity > 0:
                matched_attributes.append(
                    {
                        "key": key,
                        "name": source_spec.attribute.name,
                        "source_value": source_spec.value,
                        "candidate_value": candidate_spec.value,
                        "unit": source_spec.attribute.unit,
                        "match_strength": round(float(similarity), 2),
                    }
                )

        if possible_total <= 0:
            continue
        score = (weighted_total / possible_total) * Decimal("100")
        if score < threshold:
            continue

        available_quantity = stock_by_product.get(candidate.id, 0)
        matches.append(
            {
                "product": candidate,
                "similarity_score": round(float(score), 2),
                "matched_attributes": matched_attributes,
                "in_stock": available_quantity > 0,
                "available_quantity": available_quantity,
            }
        )

    matches.sort(
        key=lambda item: (
            not item["in_stock"],
            -item["similarity_score"],
            float(item["product"].sale_price or item["product"].price or 0),
        )
    )
    return matches[:limit]
