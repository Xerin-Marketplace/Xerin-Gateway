from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from api.config import settings


class MapConfigurationError(RuntimeError):
    pass


class MapProviderError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


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
    return {
        "country": values.get("country"),
        "country_code": values.get("country_code"),
        "region": values.get("administrative_area_level_1"),
        "city": city,
        "district": district,
        "ward": ward,
        "street": street,
        "postal_code": values.get("postal_code"),
    }


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
        return {"provider": "google", "place_id": data.get("id") or place_id, "display_name": (data.get("displayName") or {}).get("text"), "formatted_address": formatted, "latitude": Decimal(str(latitude)), "longitude": Decimal(str(longitude)), **address}

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
        return {"provider": "google", "place_id": row.get("place_id"), "display_name": None, "formatted_address": row.get("formatted_address") or f"{latitude},{longitude}", "latitude": latitude, "longitude": longitude, **address}

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
