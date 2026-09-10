from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from api.models import Category, CategoryAttribute, Product, ProductSpecification


def category_lineage(db: Session, category_id: UUID) -> list[Category]:
    lineage: list[Category] = []
    seen: set[UUID] = set()
    current = db.query(Category).filter(Category.id == category_id).first()
    if not current:
        raise HTTPException(status_code=404, detail="Category not found")
    while current:
        if current.id in seen:
            raise HTTPException(status_code=409, detail="Category hierarchy contains a cycle")
        seen.add(current.id)
        lineage.append(current)
        if not current.parent_id:
            break
        current = db.query(Category).filter(Category.id == current.parent_id).first()
    lineage.reverse()
    return lineage

def effective_category_attributes(db: Session, category_id: UUID, *, active_only: bool = True) -> list[CategoryAttribute]:
    lineage = category_lineage(db, category_id)
    selected: dict[str, CategoryAttribute] = {}
    leaf_id = lineage[-1].id
    for category in lineage:
        query = db.query(CategoryAttribute).filter(CategoryAttribute.category_id == category.id)
        if active_only:
            query = query.filter(CategoryAttribute.is_active.is_(True))
        for attribute in query.order_by(CategoryAttribute.display_order.asc(), CategoryAttribute.name.asc()).all():
            if category.id != leaf_id and not attribute.inherit_to_children:
                continue
            selected[attribute.key] = attribute  # child definitions override inherited keys
    return sorted(selected.values(), key=lambda item: (item.display_order, item.name.casefold(), item.key))


def attribute_payload(attribute: CategoryAttribute, *, requested_category_id: UUID | None = None) -> dict:
    return {
        "id": attribute.id,
        "category_id": attribute.category_id,
        "key": attribute.key,
        "name": attribute.name,
        "description": attribute.description,
        "input_type": attribute.input_type,
        "unit": attribute.unit,
        "allowed_values": attribute.allowed_values or [],
        "settings": attribute.settings or {},
        "is_required": attribute.is_required,
        "is_filterable": attribute.is_filterable,
        "is_comparable": attribute.is_comparable,
        "use_for_similarity": attribute.use_for_similarity,
        "similarity_weight": attribute.similarity_weight,
        "is_variant_attribute": attribute.is_variant_attribute,
        "inherit_to_children": attribute.inherit_to_children,
        "display_order": attribute.display_order,
        "is_active": attribute.is_active,
        "source_category_id": attribute.category_id,
        "inherited": requested_category_id is not None and attribute.category_id != requested_category_id,
        "created_at": attribute.created_at,
        "updated_at": attribute.updated_at,
    }


def _allowed_choice(attribute: CategoryAttribute, raw: str) -> str:
    choices = {str(item).strip().casefold(): str(item).strip() for item in (attribute.allowed_values or [])}
    match = choices.get(raw.strip().casefold())
    if match is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_SPECIFICATION_VALUE", "attribute": attribute.key, "message": f"Invalid value for {attribute.name}"})
    return match


def validate_specification_value(attribute: CategoryAttribute, value: Any) -> tuple[Any, str | None]:
    if value is None or value == "":
        return None, None
    kind = attribute.input_type
    if kind in {"text", "textarea", "date"}:
        clean = str(value).strip()
        return clean, clean.casefold() if clean else None
    if kind == "number":
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise HTTPException(status_code=422, detail={"code": "INVALID_SPECIFICATION_VALUE", "attribute": attribute.key, "message": f"{attribute.name} must be a number"})
        normalized = format(number.normalize(), "f")
        return float(number), normalized
    if kind == "boolean":
        if isinstance(value, bool):
            return value, "true" if value else "false"
        if str(value).strip().casefold() in {"true", "1", "yes"}: return True, "true"
        if str(value).strip().casefold() in {"false", "0", "no"}: return False, "false"
        raise HTTPException(status_code=422, detail={"code": "INVALID_SPECIFICATION_VALUE", "attribute": attribute.key, "message": f"{attribute.name} must be true or false"})
    if kind == "select":
        clean = _allowed_choice(attribute, str(value))
        return clean, clean.casefold()
    if kind == "multiselect":
        if not isinstance(value, list):
            raise HTTPException(status_code=422, detail={"code": "INVALID_SPECIFICATION_VALUE", "attribute": attribute.key, "message": f"{attribute.name} must be a list"})
        clean = [_allowed_choice(attribute, str(item)) for item in value]
        clean = list(dict.fromkeys(clean))
        return clean, "|".join(sorted(item.casefold() for item in clean))
    return value, str(value).strip().casefold()


def required_specification_errors(db: Session, product: Product) -> list[dict]:
    attrs = [item for item in effective_category_attributes(db, product.category_id) if item.is_required]
    if not attrs:
        return []
    values = {row.attribute_id: row for row in db.query(ProductSpecification).filter(ProductSpecification.product_id == product.id).all()}
    errors = []
    for attr in attrs:
        row = values.get(attr.id)
        if row is None or row.value is None or row.value == "" or row.value == []:
            errors.append({"attribute_id": str(attr.id), "key": attr.key, "name": attr.name, "message": f"{attr.name} is required"})
    return errors


def specification_payload(row: ProductSpecification) -> dict:
    attr = row.attribute
    return {
        "id": row.id, "product_id": row.product_id, "attribute_id": row.attribute_id,
        "key": attr.key, "name": attr.name, "input_type": attr.input_type, "unit": attr.unit,
        "value": row.value, "normalized_value": row.normalized_value,
        "is_comparable": attr.is_comparable, "use_for_similarity": attr.use_for_similarity,
        "similarity_weight": attr.similarity_weight, "display_order": attr.display_order,
    }
