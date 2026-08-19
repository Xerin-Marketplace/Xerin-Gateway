from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import Address
from api.services.map_location_service import (
    GoogleMapLocationClient,
    MapConfigurationError,
    MapProviderError,
)


class CustomerDeliveryLocationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "customer_delivery_location_error",
        status_code: int = 400,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def confirm_customer_map_pin(
    db: Session,
    *,
    address: Address,
    latitude: Decimal,
    longitude: Decimal,
    language: str | None = None,
) -> dict:
    """Confirm the customer's final delivery pin using the configured map provider.

    The client never marks an address verified by itself. Xerin reverse-geocodes
    the submitted final coordinates server-side, persists the canonical provider
    response, and then marks the delivery location as explicitly confirmed.
    """
    try:
        resolved = GoogleMapLocationClient().reverse_geocode(
            latitude=latitude,
            longitude=longitude,
            language=language,
        )
    except MapConfigurationError as exc:
        raise CustomerDeliveryLocationError(
            "Map/location service is not configured.",
            code="map_service_not_configured",
            status_code=503,
        ) from exc
    except MapProviderError as exc:
        raise CustomerDeliveryLocationError(
            str(exc),
            code="map_provider_error",
            status_code=502,
        ) from exc

    # Use provider-normalized values when available, but do not erase useful
    # customer-entered administrative details if the provider omits one.
    address.latitude = resolved["latitude"]
    address.longitude = resolved["longitude"]
    address.formatted_address = resolved.get("formatted_address") or address.formatted_address
    address.place_id = resolved.get("place_id") or address.place_id

    if resolved.get("country"):
        address.country = resolved["country"]
    if resolved.get("region"):
        address.region = resolved["region"]
    if resolved.get("district"):
        address.district = resolved["district"]
    if resolved.get("ward"):
        address.ward = resolved["ward"]
    if resolved.get("city"):
        address.city = resolved["city"]

    # street is non-null in the existing Address model. Only replace it when the
    # provider gave a usable street/address value.
    if resolved.get("street"):
        address.street = resolved["street"]

    if resolved.get("postal_code"):
        address.postal_code = resolved["postal_code"]

    address.location_provider = resolved.get("provider") or "google"
    address.location_confirmed_at = datetime.now(timezone.utc)
    address.is_verified = True

    db.commit()
    db.refresh(address)

    return resolved
