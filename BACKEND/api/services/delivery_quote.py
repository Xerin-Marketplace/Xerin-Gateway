from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from api.models import LogisticsCompany
from api.services.delivery_distance import (
    DeliveryDistanceError,
    calculate_seller_routes,
)
from api.services.eligible_logistics import (
    EligibleLogisticsError,
    _cart_seller_pickups,
    _customer_address,
    _company_supports_route,
    LocationFacts,
)


class DeliveryQuoteError(Exception):
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


def calculate_delivery_distance_quote(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    logistics_company_id: UUID,
    delivery_mode: str,
) -> dict:
    """Return road distance matrix for the selected eligible logistics company.

    Task 4 calculates distance only. It does not yet apply multi-seller pricing.
    """
    try:
        address = _customer_address(
            db,
            user_id=user_id,
            address_id=address_id,
            delivery_mode=delivery_mode,
        )
        sellers = _cart_seller_pickups(db, user_id=user_id)
    except EligibleLogisticsError as exc:
        raise DeliveryQuoteError(
            exc.message,
            code=exc.code,
            status_code=exc.status_code,
            extra=exc.extra,
        ) from exc

    company = (
        db.query(LogisticsCompany)
        .filter(LogisticsCompany.id == logistics_company_id)
        .first()
    )
    if company is None:
        raise DeliveryQuoteError(
            "Logistics company not found.",
            code="logistics_company_not_found",
            status_code=404,
        )

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
    route_types = []
    for seller_row in sellers:
        origin = seller_row["origin"]
        supported, route_type = _company_supports_route(company, origin, destination)
        route_types.append(route_type)
        if not supported:
            raise DeliveryQuoteError(
                "Selected logistics company cannot serve this store-to-customer route.",
                code="logistics_origin_destination_not_supported",
                status_code=409,
                extra={
                    "seller_id": str(seller_row["seller_id"]),
                    "store_id": str(seller_row["store_id"]),
                    "store_name": seller_row["store_name"],
                    "origin_country": origin.country,
                    "destination_country": destination.country,
                    "route_type": route_type,
                },
            )

    try:
        routes = calculate_seller_routes(
            sellers,
            destination_latitude=Decimal(address.latitude),
            destination_longitude=Decimal(address.longitude),
            destination_country=address.country,
        )
    except DeliveryDistanceError as exc:
        raise DeliveryQuoteError(
            exc.message,
            code=exc.code,
            status_code=exc.status_code,
        ) from exc

    if not routes:
        raise DeliveryQuoteError(
            "No seller routes could be calculated.",
            code="no_delivery_routes",
            status_code=409,
        )

    origin_by_store = {row["store_id"]: row for row in sellers}
    distances = [route.distance_km for route in routes]
    average = sum(distances, Decimal("0")) / Decimal(len(distances))

    return {
        "address_id": address.id,
        "logistics_company_id": company.id,
        "logistics_company_name": company.name,
        "delivery_mode": delivery_mode,
        "seller_count": len(routes),
        "route_types": sorted(set(route_types)),
        "distance_provider": routes[0].provider,
        "sellers": [
            {
                "seller_id": route.seller_id,
                "seller_name": origin_by_store[route.store_id]["seller_name"],
                "store_id": route.store_id,
                "store_name": route.origin_label,
                "origin_country": route.origin_country,
                "origin_region": route.origin_region,
                "route_type": route.route_type,
                "pickup_location_id": route.pickup_location_id,
                "pickup_label": route.origin_label,
                "distance_meters": route.distance_meters,
                "distance_km": route.distance_km,
                "duration_seconds": route.duration_seconds,
                "duration_minutes": route.duration_minutes,
                "provider": route.provider,
            }
            for route in routes
        ],
        "max_distance_km": max(distances),
        "min_distance_km": min(distances),
        "average_distance_km": average.quantize(Decimal("0.001")),
        "note": (
            "Google road-route distances are calculated from each product store origin. No delivery price or multi-seller pricing "
            "strategy has been applied yet."
        ),
    }
