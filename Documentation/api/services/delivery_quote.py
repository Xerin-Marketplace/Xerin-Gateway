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
    _company_covers_location,
    _eligible_services_for_destination,
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
    services = _eligible_services_for_destination(
        company,
        destination,
        delivery_mode=delivery_mode,
    )
    if not services:
        raise DeliveryQuoteError(
            "Selected logistics company does not serve the customer destination.",
            code="logistics_destination_not_covered",
            status_code=409,
        )

    for seller_row in sellers:
        pickup = seller_row["pickup"]
        origin = LocationFacts(
            country=pickup.country,
            region=pickup.region,
            city=pickup.city,
            district=pickup.district,
            ward=pickup.ward,
            postal_code=pickup.postal_code,
            latitude=pickup.latitude,
            longitude=pickup.longitude,
        )
        if not _company_covers_location(company, origin):
            raise DeliveryQuoteError(
                "Selected logistics company cannot serve every seller pickup location.",
                code="logistics_pickup_not_covered",
                status_code=409,
                extra={
                    "seller_id": str(seller_row["seller_id"]),
                    "pickup_location_id": str(pickup.id),
                },
            )

    try:
        routes = calculate_seller_routes(
            sellers,
            destination_latitude=Decimal(address.latitude),
            destination_longitude=Decimal(address.longitude),
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

    seller_by_id = {row["seller_id"]: row for row in sellers}
    distances = [route.distance_km for route in routes]
    average = sum(distances, Decimal("0")) / Decimal(len(distances))

    return {
        "address_id": address.id,
        "logistics_company_id": company.id,
        "logistics_company_name": company.name,
        "delivery_mode": delivery_mode,
        "seller_count": len(routes),
        "distance_provider": routes[0].provider,
        "sellers": [
            {
                "seller_id": route.seller_id,
                "seller_name": seller_by_id[route.seller_id]["seller_name"],
                "pickup_location_id": route.pickup_location_id,
                "pickup_label": seller_by_id[route.seller_id]["pickup"].label,
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
            "Road-route distances only. No delivery price or multi-seller pricing "
            "strategy has been applied yet."
        ),
    }
