from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from api.enums import LogisticsCompanyStatus, LogisticsScope
from api.models import (
    Address,
    Cart,
    CartItem,
    LogisticsCompany,
    ProductStatus,
    SellerPickupLocation,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)



class EligibleLogisticsError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        extra: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.extra = extra or {}


@dataclass(frozen=True)
class LocationFacts:
    country: str
    region: str
    city: str


def _norm(value: str | None) -> str:
    return (value or "").strip().casefold()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _scope_supports(scope, requested: str) -> bool:
    value = _enum_value(scope)
    if requested == "local":
        return value in {"local", "both"}
    return value in {"international", "both"}


def _zone_matches_location(zone: ShippingZone, location: LocationFacts) -> bool:
    if not zone.is_active:
        return False
    if _norm(zone.country) != _norm(location.country):
        return False

    region_rules = {_norm(item) for item in (zone.regions or []) if _norm(item)}
    city_rules = {_norm(item) for item in (zone.cities or []) if _norm(item)}

    if region_rules and _norm(location.region) not in region_rules:
        return False
    if city_rules and _norm(location.city) not in city_rules:
        return False
    return True


def _address_is_tanzania(address: Address) -> bool:
    return _norm(address.country) in {
        "tanzania",
        "united republic of tanzania",
        "tz",
    }


def _customer_address(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    delivery_mode: str,
) -> Address:
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == user_id)
        .first()
    )
    if address is None:
        raise EligibleLogisticsError(
            "Delivery address not found.",
            code="delivery_address_not_found",
            status_code=404,
        )

    if not address.delivery_ready:
        raise EligibleLogisticsError(
            "Confirm the exact delivery map pin and recipient details before selecting a logistics company.",
            code="delivery_address_not_ready",
            status_code=409,
            extra={"address_id": str(address.id)},
        )

    local = _address_is_tanzania(address)
    if delivery_mode == "local" and not local:
        raise EligibleLogisticsError(
            "Local delivery requires a Tanzania delivery address.",
            code="local_delivery_address_required",
            status_code=422,
        )
    if delivery_mode == "international" and local:
        raise EligibleLogisticsError(
            "International delivery requires a non-Tanzania delivery address.",
            code="international_delivery_address_required",
            status_code=422,
        )
    return address


def _cart_seller_pickups(
    db: Session,
    *,
    user_id: UUID,
) -> list[dict]:
    cart = (
        db.query(Cart)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product),
        )
        .filter(Cart.user_id == user_id)
        .first()
    )
    if cart is None or not cart.items:
        raise EligibleLogisticsError(
            "Cart is empty.",
            code="cart_empty",
            status_code=400,
        )

    seller_map: dict[UUID, object] = {}
    for item in cart.items:
        product = item.product
        if (
            product is None
            or not product.is_active
            or product.status != ProductStatus.approved
        ):
            continue
        seller_map[product.seller_id] = product.seller

    if not seller_map:
        raise EligibleLogisticsError(
            "Cart does not contain any shippable products.",
            code="cart_has_no_shippable_products",
            status_code=409,
        )

    seller_ids = list(seller_map.keys())
    pickups = (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id.in_(seller_ids),
            SellerPickupLocation.is_active.is_(True),
            SellerPickupLocation.is_default.is_(True),
        )
        .order_by(SellerPickupLocation.created_at.desc())
        .all()
    )
    pickup_by_seller = {row.seller_id: row for row in pickups}

    missing = [
        {
            "seller_id": str(seller_id),
            "seller_name": getattr(seller_map[seller_id], "business_name", str(seller_id)),
        }
        for seller_id in seller_ids
        if seller_id not in pickup_by_seller
    ]
    if missing:
        raise EligibleLogisticsError(
            "One or more sellers do not have an active default pickup location.",
            code="seller_pickup_location_required",
            status_code=409,
            extra={"sellers": missing},
        )

    result = []
    for seller_id in seller_ids:
        seller = seller_map[seller_id]
        pickup = pickup_by_seller[seller_id]
        if pickup.latitude is None or pickup.longitude is None:
            raise EligibleLogisticsError(
                "One or more seller pickup locations do not contain GPS coordinates.",
                code="seller_pickup_gps_required",
                status_code=409,
                extra={
                    "seller_id": str(seller_id),
                    "pickup_location_id": str(pickup.id),
                },
            )

        result.append(
            {
                "seller_id": seller_id,
                "seller_name": seller.business_name,
                "pickup": pickup,
            }
        )

    return result


def _company_methods_with_rates(
    db: Session,
    *,
    delivery_mode: str,
    search: str | None,
    supports_cod: bool | None,
    supports_tracking: bool | None,
) -> list[LogisticsCompany]:
    query = (
        db.query(LogisticsCompany)
        .options(
            selectinload(LogisticsCompany.services)
            .selectinload(ShippingMethod.rates)
            .joinedload(ShippingRate.zone)
        )
        .filter(LogisticsCompany.status == LogisticsCompanyStatus.active)
    )

    # Company itself must support the requested delivery scope.
    if delivery_mode == "local":
        query = query.filter(
            LogisticsCompany.scope.in_([LogisticsScope.local, LogisticsScope.both])
        )
    else:
        query = query.filter(
            LogisticsCompany.scope.in_(
                [LogisticsScope.international, LogisticsScope.both]
            )
        )

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                LogisticsCompany.name.ilike(term),
                LogisticsCompany.code.ilike(term),
            )
        )

    if supports_cod is not None:
        query = query.filter(LogisticsCompany.supports_cod.is_(supports_cod))
    if supports_tracking is not None:
        query = query.filter(
            LogisticsCompany.supports_tracking.is_(supports_tracking)
        )

    return query.order_by(LogisticsCompany.name.asc()).all()


def _company_covers_location(
    company: LogisticsCompany,
    location: LocationFacts,
    *,
    delivery_mode: str | None = None,
) -> bool:
    for method in company.services:
        if not method.is_active:
            continue
        if delivery_mode is not None and not _scope_supports(
            method.scope, delivery_mode
        ):
            continue

        for rate in method.rates:
            if not rate.is_active or rate.zone is None:
                continue
            if delivery_mode is not None and not _scope_supports(
                rate.zone.scope, delivery_mode
            ):
                continue
            if _zone_matches_location(rate.zone, location):
                return True

    return False


def _eligible_services_for_destination(
    company: LogisticsCompany,
    destination: LocationFacts,
    *,
    delivery_mode: str,
) -> list[dict]:
    results: dict[UUID, dict] = {}

    for method in company.services:
        if not method.is_active or not _scope_supports(method.scope, delivery_mode):
            continue

        has_matching_rate = any(
            rate.is_active
            and rate.zone is not None
            and _scope_supports(rate.zone.scope, delivery_mode)
            and _zone_matches_location(rate.zone, destination)
            for rate in method.rates
        )
        if not has_matching_rate:
            continue

        results[method.id] = {
            "method_id": method.id,
            "method_name": method.name,
            "service_code": method.service_code,
            "scope": method.scope,
            "min_delivery_days": method.min_delivery_days,
            "max_delivery_days": method.max_delivery_days,
            "supports_cod": bool(method.supports_cod and company.supports_cod),
            "supports_tracking": bool(
                method.supports_tracking and company.supports_tracking
            ),
        }

    return sorted(results.values(), key=lambda row: row["method_name"].casefold())


def find_eligible_logistics_companies(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    delivery_mode: str,
    page: int,
    page_size: int,
    search: str | None = None,
    supports_cod: bool | None = None,
    supports_tracking: bool | None = None,
) -> dict:
    """Return logistics companies capable of serving the entire current cart.

    Eligibility requires:
    1. customer's delivery address is explicitly map-confirmed;
    2. every shippable seller in the cart has an active default pickup point;
    3. logistics company is active and supports the requested local/international scope;
    4. company has destination service coverage;
    5. the same company has zone coverage for every seller pickup origin.

    Task 3 intentionally does not calculate prices or distances. Those are Phase 2
    Tasks 4/5. This task answers only: "Who can serve this complete order?"
    """
    address = _customer_address(
        db,
        user_id=user_id,
        address_id=address_id,
        delivery_mode=delivery_mode,
    )
    sellers = _cart_seller_pickups(db, user_id=user_id)

    destination = LocationFacts(
        country=address.country,
        region=address.region,
        city=address.city,
    )

    companies = _company_methods_with_rates(
        db,
        delivery_mode=delivery_mode,
        search=search,
        supports_cod=supports_cod,
        supports_tracking=supports_tracking,
    )

    eligible = []
    for company in companies:
        destination_services = _eligible_services_for_destination(
            company,
            destination,
            delivery_mode=delivery_mode,
        )
        if not destination_services:
            continue

        covered = 0
        all_pickups_covered = True
        for seller_row in sellers:
            pickup = seller_row["pickup"]
            origin = LocationFacts(
                country=pickup.country,
                region=pickup.region,
                city=pickup.city,
            )

            # Origin coverage is intentionally scope-neutral. An international
            # carrier may use a local/both Tanzania pickup zone and an
            # international destination zone for the same end-to-end shipment.
            if _company_covers_location(company, origin):
                covered += 1
            else:
                all_pickups_covered = False
                break

        if not all_pickups_covered:
            continue

        eligible.append(
            {
                "logistics_company_id": company.id,
                "name": company.name,
                "code": company.code,
                "scope": company.scope,
                "supports_cod": bool(company.supports_cod),
                "supports_tracking": bool(company.supports_tracking),
                "supports_webhooks": bool(company.supports_webhooks),
                "seller_count": len(sellers),
                "covered_seller_count": covered,
                "services": destination_services,
            }
        )

    total = len(eligible)
    total_pages = ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    page_rows = eligible[start : start + page_size]

    return {
        "address_id": address.id,
        "delivery_mode": delivery_mode,
        "seller_count": len(sellers),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "sellers": [
            {
                "seller_id": row["seller_id"],
                "seller_name": row["seller_name"],
                "pickup_location_id": row["pickup"].id,
                "pickup_label": row["pickup"].label,
                "country": row["pickup"].country,
                "region": row["pickup"].region,
                "city": row["pickup"].city,
                "latitude": Decimal(row["pickup"].latitude),
                "longitude": Decimal(row["pickup"].longitude),
            }
            for row in sellers
        ],
        "results": page_rows,
    }
