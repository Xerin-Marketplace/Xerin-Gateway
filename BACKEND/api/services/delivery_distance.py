from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from api.services.map_location_service import (
    GoogleMapLocationClient,
    MapConfigurationError,
    MapProviderError,
)


class DeliveryDistanceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "delivery_distance_error",
        status_code: int = 502,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class SellerRouteDistance:
    seller_id: UUID
    store_id: UUID
    origin_reference_id: UUID
    origin_label: str
    origin_country: str
    origin_region: str
    route_type: str
    pickup_location_id: UUID
    distance_meters: int
    distance_km: Decimal
    duration_seconds: int
    duration_minutes: Decimal
    provider: str


def calculate_seller_routes(
    sellers: Iterable[dict],
    *,
    destination_latitude: Decimal,
    destination_longitude: Decimal,
    destination_country: str | None = None,
) -> list[SellerRouteDistance]:
    """Calculate Google road distance from each cart store origin to customer.

    The Phase 3 resolved `row["origin"]` is authoritative. This is essential for
    sellers with stores in different countries. A seller default pickup may
    already have been used by Phase 3 only as a compatibility fallback.
    """
    client = GoogleMapLocationClient()
    routes: list[SellerRouteDistance] = []

    for row in sellers:
        origin = row["origin"]
        if origin.latitude is None or origin.longitude is None:
            raise DeliveryDistanceError(
                "Store shipping origin does not contain GPS coordinates.",
                code="store_origin_gps_required",
                status_code=409,
            )

        try:
            route = client.compute_route_distance(
                origin_latitude=origin.latitude,
                origin_longitude=origin.longitude,
                destination_latitude=destination_latitude,
                destination_longitude=destination_longitude,
            )
        except MapConfigurationError as exc:
            raise DeliveryDistanceError(
                "Road-distance service is not configured.",
                code="route_service_not_configured",
                status_code=503,
            ) from exc
        except MapProviderError as exc:
            raise DeliveryDistanceError(
                str(exc), code="route_provider_error", status_code=502
            ) from exc

        same_country = (origin.country or "").strip().casefold() == (
            destination_country or ""
        ).strip().casefold()
        pickup = row.get("pickup")
        origin_reference_id = row["store_id"]
        routes.append(
            SellerRouteDistance(
                seller_id=row["seller_id"],
                store_id=row["store_id"],
                origin_reference_id=origin_reference_id,
                origin_label=row["store_name"],
                origin_country=origin.country,
                origin_region=origin.region,
                route_type="domestic" if same_country else "cross_border",
                # Kept for API/order snapshot compatibility. For store-based
                # routes it identifies the store when no pickup exists.
                pickup_location_id=pickup.id if pickup is not None else row["store_id"],
                distance_meters=int(route["distance_meters"]),
                distance_km=Decimal(str(route["distance_km"])),
                duration_seconds=int(route["duration_seconds"]),
                duration_minutes=Decimal(str(route["duration_minutes"])),
                provider=str(route["provider"]),
            )
        )
    return routes

