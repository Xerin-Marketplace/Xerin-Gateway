from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from api.enums import MultiSellerPricingStrategy, ShippingRateType
from api.models import Address, LogisticsCompany, ShippingMethod, ShippingRate
from api.services.delivery_quote import (
    DeliveryQuoteError,
    calculate_delivery_distance_quote,
)
from api.services.eligible_logistics import (
    LocationFacts,
    _zone_matches_location,
    _zone_supports_capability,
)
from api.services.fx_service import FxRateUnavailableError, convert_amount_to_tzs


MONEY = Decimal("0.01")
DISTANCE = Decimal("0.001")


class MultiSellerPricingError(Exception):
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


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _distance(value: Decimal) -> Decimal:
    return value.quantize(DISTANCE, rounding=ROUND_HALF_UP)


def _strategy_distance(
    strategy: MultiSellerPricingStrategy,
    routes: list[dict],
) -> tuple[Decimal, UUID | None]:
    if not routes:
        raise MultiSellerPricingError(
            "No seller route distances are available.",
            code="no_seller_routes",
            status_code=409,
        )

    if strategy == MultiSellerPricingStrategy.farthest_seller:
        farthest = max(routes, key=lambda row: Decimal(row["distance_km"]))
        return _distance(Decimal(farthest["distance_km"])), farthest["seller_id"]

    if strategy == MultiSellerPricingStrategy.sum_individual:
        total = sum(
            (Decimal(row["distance_km"]) for row in routes),
            Decimal("0"),
        )
        return _distance(total), None

    if strategy == MultiSellerPricingStrategy.optimized_multi_pickup:
        raise MultiSellerPricingError(
            "Optimized multi-pickup route pricing is reserved for a future routing phase.",
            code="optimized_multi_pickup_not_available",
            status_code=409,
        )

    if strategy == MultiSellerPricingStrategy.logistics_provider_quote:
        raise MultiSellerPricingError(
            "Provider-native multi-seller quote pricing is not enabled yet.",
            code="logistics_provider_quote_not_available",
            status_code=409,
        )

    raise MultiSellerPricingError(
        "Unsupported multi-seller pricing strategy.",
        code="unsupported_multi_seller_strategy",
        status_code=422,
    )


def _calculate_amount(
    rate: ShippingRate,
    *,
    billable_distance_km: Decimal,
) -> tuple[Decimal, dict]:
    rate_type = rate.rate_type
    base = Decimal(rate.base_amount or 0)
    per_km = Decimal(rate.amount_per_km or 0)

    if rate.max_distance_km is not None and (
        billable_distance_km > Decimal(rate.max_distance_km)
    ):
        raise MultiSellerPricingError(
            "Delivery route exceeds this logistics rate's maximum distance.",
            code="shipping_rate_max_distance_exceeded",
            status_code=409,
            extra={
                "rate_id": str(rate.id),
                "max_distance_km": str(rate.max_distance_km),
                "billable_distance_km": str(billable_distance_km),
            },
        )

    if rate_type == ShippingRateType.free:
        raw = Decimal("0")
        amount = Decimal("0")
    elif rate_type == ShippingRateType.flat:
        raw = base
        amount = base
    elif rate_type == ShippingRateType.per_km:
        raw = per_km * billable_distance_km
        amount = raw
    elif rate_type == ShippingRateType.base_plus_per_km:
        raw = base + (per_km * billable_distance_km)
        amount = raw
    elif rate_type == ShippingRateType.weight_based:
        # Weight pricing remains supported by the legacy /shipping/quote
        # endpoint. Task 5 only presents route-based multi-seller pricing.
        raise MultiSellerPricingError(
            "Weight-based rate is not a route-based multi-seller pricing option.",
            code="weight_based_rate_not_supported_here",
            status_code=409,
        )
    elif rate_type == ShippingRateType.provider_quote:
        raise MultiSellerPricingError(
            "Provider quote rate requires the provider-native quote flow.",
            code="provider_quote_rate_not_available",
            status_code=409,
        )
    else:
        raise MultiSellerPricingError(
            "Unsupported shipping rate type.",
            code="unsupported_shipping_rate_type",
            status_code=422,
        )

    minimum_applied = False
    maximum_applied = False

    if rate.minimum_fee is not None and amount < Decimal(rate.minimum_fee):
        amount = Decimal(rate.minimum_fee)
        minimum_applied = True

    if rate.maximum_fee is not None and amount > Decimal(rate.maximum_fee):
        amount = Decimal(rate.maximum_fee)
        maximum_applied = True

    return _money(amount), {
        "base_amount": _money(base),
        "amount_per_km": _money(per_km),
        "raw_distance_amount": _money(raw),
        "minimum_fee": (
            _money(Decimal(rate.minimum_fee))
            if rate.minimum_fee is not None
            else None
        ),
        "maximum_fee": (
            _money(Decimal(rate.maximum_fee))
            if rate.maximum_fee is not None
            else None
        ),
        "minimum_fee_applied": minimum_applied,
        "maximum_fee_applied": maximum_applied,
    }


def calculate_multi_seller_delivery_pricing(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    logistics_company_id: UUID,
    delivery_mode: str,
    method_id: UUID | None = None,
) -> dict:
    """Apply the logistics company's configured multi-seller pricing strategy.

    Launch default:
        FARTHEST_SELLER

    Example:
        seller routes = 7km, 5km, 3km
        billable distance = 7km

    This endpoint calculates/presents the delivery amount but does not freeze it
    into an order yet. Phase 2 Task 6 handles checkout total + quote snapshot.
    """
    try:
        distance_quote = calculate_delivery_distance_quote(
            db,
            user_id=user_id,
            address_id=address_id,
            logistics_company_id=logistics_company_id,
            delivery_mode=delivery_mode,
        )
    except DeliveryQuoteError as exc:
        raise MultiSellerPricingError(
            exc.message,
            code=exc.code,
            status_code=exc.status_code,
            extra=exc.extra,
        ) from exc

    company = db.get(LogisticsCompany, logistics_company_id)
    if company is None:
        raise MultiSellerPricingError(
            "Logistics company not found.",
            code="logistics_company_not_found",
            status_code=404,
        )

    strategy = company.multi_seller_pricing_strategy
    billable_distance, billable_seller_id = _strategy_distance(
        strategy,
        distance_quote["sellers"],
    )

    address = db.get(Address, address_id)
    destination = LocationFacts(
        country=address.country,
        region=address.region,
        city=address.city,
        district=address.district,
        ward=address.ward,
        postal_code=address.postal_code,
        latitude=address.latitude,
        longitude=address.longitude,
    )

    query = (
        db.query(ShippingRate)
        .options(
            joinedload(ShippingRate.zone),
            joinedload(ShippingRate.method),
        )
        .join(ShippingMethod, ShippingRate.method_id == ShippingMethod.id)
        .filter(
            ShippingMethod.logistics_company_id == logistics_company_id,
            ShippingMethod.is_active.is_(True),
            ShippingRate.is_active.is_(True),
        )
    )
    if method_id is not None:
        query = query.filter(ShippingRate.method_id == method_id)

    rates = query.all()
    options = []

    for rate in rates:
        if (
            rate.zone is None
            or rate.zone.logistics_company_id not in (None, company.id)
            or not _zone_matches_location(rate.zone, destination)
        ):
            continue

        route_types = set(distance_quote.get("route_types") or [])
        if "cross_border" in route_types:
            if not _zone_supports_capability(rate.zone, "supports_cross_border_inbound"):
                continue
        elif "domestic" in route_types:
            if not _zone_supports_capability(rate.zone, "supports_domestic_delivery"):
                continue

        method = rate.method
        try:
            amount, breakdown = _calculate_amount(
                rate,
                billable_distance_km=billable_distance,
            )
        except MultiSellerPricingError as exc:
            # A company can have several methods/rates. An incompatible rate
            # should not hide otherwise valid options.
            if exc.code in {
                "weight_based_rate_not_supported_here",
                "provider_quote_rate_not_available",
                "shipping_rate_max_distance_exceeded",
            }:
                continue
            raise

        try:
            amount = convert_amount_to_tzs(db, amount, rate.currency)
            for key in ("base_amount", "amount_per_km", "raw_distance_amount", "minimum_fee", "maximum_fee"):
                value = breakdown.get(key)
                if value is not None:
                    breakdown[key] = convert_amount_to_tzs(db, value, rate.currency)
        except FxRateUnavailableError:
            # A logistics rate without an active TZS conversion cannot be used
            # in a TZS-settled checkout.
            continue

        seller_rows = []
        for route in distance_quote["sellers"]:
            seller_rows.append(
                {
                    "seller_id": route["seller_id"],
                    "seller_name": route["seller_name"],
                    "store_id": route.get("store_id"),
                    "store_name": route.get("store_name"),
                    "origin_country": route.get("origin_country"),
                    "origin_region": route.get("origin_region"),
                    "route_type": route.get("route_type"),
                    "pickup_location_id": route["pickup_location_id"],
                    "pickup_label": route["pickup_label"],
                    "distance_km": _distance(Decimal(route["distance_km"])),
                    "duration_minutes": Decimal(str(route["duration_minutes"])),
                    "is_billable_reference": (
                        billable_seller_id is not None
                        and route["seller_id"] == billable_seller_id
                    ),
                }
            )

        options.append(
            {
                "rate_id": rate.id,
                "method_id": method.id,
                "method_name": method.name,
                "service_code": method.service_code,
                "logistics_company_id": company.id,
                "logistics_company_name": company.name,
                "strategy": strategy,
                "rate_type": rate.rate_type,
                "currency": "TZS",
                "seller_count": len(distance_quote["sellers"]),
                "billable_distance_km": billable_distance,
                "billable_seller_id": billable_seller_id,
                "delivery_amount": amount,
                "min_delivery_days": method.min_delivery_days,
                "max_delivery_days": method.max_delivery_days,
                "supports_cod": bool(method.supports_cod and company.supports_cod),
                "supports_tracking": bool(
                    method.supports_tracking and company.supports_tracking
                ),
                "pricing_breakdown": breakdown,
                "sellers": seller_rows,
            }
        )

    options.sort(key=lambda row: (row["delivery_amount"], row["method_name"]))

    if not options:
        raise MultiSellerPricingError(
            "Selected logistics company has no active compatible route-based delivery rate for this destination.",
            code="no_multi_seller_delivery_rate",
            status_code=409,
        )

    return {
        "address_id": address_id,
        "logistics_company_id": company.id,
        "logistics_company_name": company.name,
        "delivery_mode": delivery_mode,
        "strategy": strategy,
        "seller_count": len(distance_quote["sellers"]),
        "options": options,
        "note": (
            "Delivery pricing is calculated using the logistics company's configured "
            "multi-seller strategy. The current launch default is FARTHEST_SELLER. "
            "This quote is not yet frozen into an order."
        ),
    }
