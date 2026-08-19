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
) -> list[SellerRouteDistance]:
    """Calculate actual road distance from each seller pickup to customer.

    Each seller is calculated independently because Phase 2 Task 5 will apply
    configurable multi-seller strategies such as FARTHEST_SELLER.
    """
    client = GoogleMapLocationClient()
    routes: list[SellerRouteDistance] = []

    for row in sellers:
        pickup = row["pickup"]

        try:
            route = client.compute_route_distance(
                origin_latitude=pickup.latitude,
                origin_longitude=pickup.longitude,
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
                str(exc),
                code="route_provider_error",
                status_code=502,
            ) from exc

        routes.append(
            SellerRouteDistance(
                seller_id=row["seller_id"],
                pickup_location_id=pickup.id,
                distance_meters=int(route["distance_meters"]),
                distance_km=Decimal(str(route["distance_km"])),
                duration_seconds=int(route["duration_seconds"]),
                duration_minutes=Decimal(str(route["duration_minutes"])),
                provider=str(route["provider"]),
            )
        )

    return routes
