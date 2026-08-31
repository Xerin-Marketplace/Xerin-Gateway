from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
import re
from urllib import response

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy import exc
from urllib3.util.retry import Retry
import json
from api.config import settings


class MapConfigurationError(RuntimeError):
    pass

class MapProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


# F8: map providers are allowed to use their own spelling/labels, but Xerin's
# routing engine must persist canonical administrative names.  Keep aliases
# intentionally small and explicit so we never "guess" unrelated worldwide
# locations.  New provider aliases can be added here without touching checkout.
_CANONICAL_LOCATION_ALIASES: dict[str, str] = {
    "dar es salam": "Dar es Salaam",
    "dar es salaam": "Dar es Salaam",
    "united republic of tanzania": "Tanzania",
    "tanzania, united republic of": "Tanzania",
}


def canonical_location_name(value: str | None) -> str | None:
    """Return a stable Xerin label for a provider-supplied location value."""
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        return None
    return _CANONICAL_LOCATION_ALIASES.get(cleaned.casefold(), cleaned)


def canonical_formatted_address(value: str | None) -> str | None:
    """Normalize known provider spelling aliases without destroying display text."""
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        return None
    # Google may return "Dar es Salam" in formatted_address even while Xerin's
    # canonical region is "Dar es Salaam".  Normalize the display text too so
    # the user does not see a spelling that will later fail route matching.
    cleaned = re.sub(r"\bDar\s+es\s+Salam\b", "Dar es Salaam", cleaned, flags=re.IGNORECASE)
    return cleaned


def _canonicalize_address_fields(address: dict[str, str | None]) -> dict[str, str | None]:
    normalized = dict(address)
    for key in ("country", "region", "city", "district", "ward"):
        normalized[key] = canonical_location_name(normalized.get(key))
    return normalized


def _request_session() -> requests.Session:
    retry = Retry(total=2, connect=2, read=2, status=2, backoff_factor=0.25, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET", "POST"}), raise_on_status=False)
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
    session.mount("https://", adapter)
    return session


def _component_map_new(components: list[dict[str, Any]] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for component in components or []:
        text = component.get("longText") or component.get("shortText")
        if not text:
            continue
        types = component.get("types") or []
        for component_type in types:
            values.setdefault(str(component_type), str(text))
        if "country" in types and component.get("shortText"):
            values["country_code"] = str(component["shortText"]).upper()
    return values

def _component_map_legacy(components: list[dict[str, Any]] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    for component in components or []:
        text = component.get("long_name") or component.get("short_name")
        if not text:
            continue
        types = component.get("types") or []
        for component_type in types:
            values.setdefault(str(component_type), str(text))
        if "country" in types and component.get("short_name"):
            values["country_code"] = str(component["short_name"]).upper()
    return values


def _address_fields(values: dict[str, str]) -> dict[str, str | None]:
    city = values.get("locality") or values.get("postal_town") or values.get("administrative_area_level_2") or values.get("sublocality_level_1")
    district = values.get("administrative_area_level_2") or values.get("sublocality_level_1") or values.get("sublocality")
    ward = values.get("administrative_area_level_3") or values.get("sublocality_level_2") or values.get("neighborhood")
    street = " ".join(part for part in (values.get("street_number"), values.get("route")) if part) or None
    return _canonicalize_address_fields({
        "country": values.get("country"),
        "country_code": values.get("country_code"),
        "region": values.get("administrative_area_level_1"),
        "city": city,
        "district": district,
        "ward": ward,
        "street": street,
        "postal_code": values.get("postal_code"),
    })

@dataclass
class GoogleMapLocationClient:
    timeout: int = settings.MAP_API_TIMEOUT_SECONDS

    def __post_init__(self):
        self.session = _request_session()

    @property
    def api_key(self) -> str:
        key = (settings.GOOGLE_MAPS_API_KEY or "").strip()
        if not key:
            raise MapConfigurationError("GOOGLE_MAPS_API_KEY is not configured")
        return key
    
    def _json_response(self, response):
        """Normalize response to JSON and raise on HTTP error."""
        try:
            data = response.json() if hasattr(response, "json") else json.loads(response.text)
        except Exception as e:
            raise RuntimeError(f"Invalid JSON response from map service: {e}")
        status = getattr(response, "status_code", None) or getattr(response, "status", None)
        if status is not None and int(status) >= 400:
            raise RuntimeError(f"Map service error {status}: {data}")
        return data

    def autocomplete(self, *, query: str, session_token: str | None = None, country_code: str | None = None, language: str | None = None, limit: int = 8) -> list[dict[str, str | None]]:
        body: dict[str, Any] = {"input": query, "languageCode": language or settings.MAP_DEFAULT_LANGUAGE}
        region = (country_code or settings.MAP_DEFAULT_COUNTRY_CODE).strip().lower()
        if region:
            body["includedRegionCodes"] = [region]
        if session_token:
            body["sessionToken"] = session_token
        response = self.session.post(
            f"{settings.GOOGLE_PLACES_BASE_URL.rstrip('/')}/v1/places:autocomplete",
            json=body,
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": "suggestions.placePrediction.placeId,suggestions.placePrediction.text,suggestions.placePrediction.structuredFormat"},
            timeout=self.timeout,
        )
        self._ensure_ok(response, "Google Places autocomplete failed")
        data = response.json()
        results: list[dict[str, str | None]] = []
        for suggestion in data.get("suggestions") or []:
            prediction = suggestion.get("placePrediction") or {}
            place_id = prediction.get("placeId")
            text = (prediction.get("text") or {}).get("text")
            if not place_id or not text:
                continue
            structured = prediction.get("structuredFormat") or {}
            results.append({"place_id": str(place_id), "description": str(text), "main_text": (structured.get("mainText") or {}).get("text"), "secondary_text": (structured.get("secondaryText") or {}).get("text")})
            if len(results) >= limit:
                break
        return results
        
    def place_details(self, *, place_id: str, session_token: str | None = None, language: str | None = None, region_code: str | None = None) -> dict[str, Any]:
        params: dict[str, str] = {"languageCode": language or settings.MAP_DEFAULT_LANGUAGE}
        if session_token:
            params["sessionToken"] = session_token
        if region_code:
            params["regionCode"] = region_code.upper()
        response = self.session.get(
            f"{settings.GOOGLE_PLACES_BASE_URL.rstrip('/')}/v1/places/{place_id}",
            params=params,
            headers={"X-Goog-Api-Key": self.api_key, "X-Goog-FieldMask": "id,displayName,formattedAddress,location,addressComponents"},
            timeout=self.timeout,
        )
        self._ensure_ok(response, "Google Place Details failed")
        data = response.json()
        location = data.get("location") or {}
        latitude, longitude, formatted = location.get("latitude"), location.get("longitude"), data.get("formattedAddress")
        if latitude is None or longitude is None or not formatted:
            raise MapProviderError("Selected place did not contain a usable address and coordinates")
        address = _address_fields(_component_map_new(data.get("addressComponents")))
        return {"provider": "google", "place_id": data.get("id") or place_id, "display_name": (data.get("displayName") or {}).get("text"), "formatted_address": canonical_formatted_address(formatted), "latitude": Decimal(str(latitude)), "longitude": Decimal(str(longitude)), **address}
    

    def reverse_geocode(self, *, latitude: Decimal, longitude: Decimal, language: str | None = None) -> dict[str, Any]:
        response = self.session.get(settings.GOOGLE_GEOCODING_BASE_URL, params={"latlng": f"{latitude},{longitude}", "language": language or settings.MAP_DEFAULT_LANGUAGE, "key": self.api_key}, timeout=self.timeout)
        self._ensure_ok(response, "Google reverse geocoding failed")
        data = response.json()
        if data.get("status") not in {"OK", "ZERO_RESULTS"}:
            raise MapProviderError(data.get("error_message") or f"Google geocoding status: {data.get('status')}")
        rows = data.get("results") or []
        if not rows:
            raise MapProviderError("No address was found for the selected map point")
        row = rows[0]
        address = _address_fields(_component_map_legacy(row.get("address_components")))
        return {"provider": "google", "place_id": row.get("place_id"), "display_name": None, "formatted_address": canonical_formatted_address(row.get("formatted_address")) or f"{latitude},{longitude}", "latitude": latitude, "longitude": longitude, **address}

    @staticmethod
    def _ensure_ok(response: requests.Response, message: str) -> None:
        if response.ok:
            return
        detail = message
        try:
            data = response.json()
            provider_message = (data.get("error") or {}).get("message") or data.get("error_message")
            if provider_message:
                detail = f"{message}: {provider_message}"
        except ValueError:
            pass
        raise MapProviderError(detail, status_code=response.status_code)

    def compute_route_distance(
        self,
        *,
        origin_latitude: Decimal | float, 
        origin_longitude: Decimal | float,    
        destination_latitude: Decimal | float, 
        destination_longitude: Decimal | float,
        travel_mode: str | None = None,
        routing_preference: str | None = None,
    ) -> dict:
        """Return road-route distance/duration using Google Routes API.

        Phase 2 Task 4 deliberately centralizes route distance here so pricing 
        logic never uses straight-line/Haversine distance for customer billing.
        """
        if not settings.GOOGLE_MAPS_API_KEY:
            raise MapConfigurationError("GOOGLE_MAPS_API_KEY is not configured")

        url = f"{settings.GOOGLE_ROUTES_BASE_URL.rstrip('/')}/directions/v2:computeRoutes"
        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": float(origin_latitude),
                        "longitude": float(origin_longitude),
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": float(destination_latitude),
                        "longitude": float(destination_longitude),
                    }
                }
            },
            "travelMode": travel_mode or settings.MAP_ROUTE_TRAVEL_MODE,
            "routingPreference": (
                routing_preference or settings.MAP_ROUTE_ROUTING_PREFERENCE
            ),
            "computeAlternativeRoutes": False,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
            "X-Goog-FieldMask": "routes.distanceMeters,routes.duration",
        }
        try:
            response = self.session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise MapProviderError(
                "Could not reach map route provider."
            ) from exc

        data = self._json_response(response)
        if not response.ok:
            message = (
                data.get("error", {}).get("message")
                if isinstance(data, dict)
                else None
            )
            raise MapProviderError(
                message or "Map route provider request failed."
            )

        routes = data.get("routes") or []
        if not routes:
            raise MapProviderError("No drivable route was found.")

        route = routes[0]
        distance_meters = int(route.get("distanceMeters") or 0)
        duration_raw = str(route.get("duration") or "0s")
        try:
            duration_seconds = int(float(duration_raw.rstrip("s") or 0))
        except ValueError:
            duration_seconds = 0

        return {
        "provider": "google",
        "distance_meters": distance_meters,
        "distance_km": round(distance_meters / 1000.0, 3),
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_seconds / 60.0, 1),
        "travel_mode": travel_mode or settings.MAP_ROUTE_TRAVEL_MODE,
        }


