"""Location lookup service (autocomplete, place details, reverse geocode).

Provider chain:
  * Google Places/Geocoding when GOOGLE_MAPS_API_KEY is configured
  * Nominatim (OpenStreetMap) otherwise — free, no key required

Both produce the same MapResolvedLocation shape consumed by web + mobile.
"""

from __future__ import annotations

import re
from typing import Any

import requests

from api.config import settings

GOOGLE_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
GOOGLE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

NOMINATIM_SEARCH_URL = "/search"
NOMINATIM_LOOKUP_URL = "/lookup"
NOMINATIM_REVERSE_URL = "/reverse"

class MapServiceError(Exception):
    """Raised when the configured map provider fails or returns nothing."""


def active_provider() -> str:
    return "google" if settings.GOOGLE_MAPS_API_KEY else "nominatim"


def _request(url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> Any:
    try:
        resp = requests.get(url, params=params, headers=headers or {}, timeout=settings.MAP_REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        raise MapServiceError(f"Map provider request failed: {exc}") from exc
    except ValueError as exc:
        raise MapServiceError("Map provider returned an invalid response.") from exc


# ------------------------------------------------------------- shared shaping

def _empty_location(**overrides: Any) -> dict[str, Any]:
    base = {
        "provider": active_provider(),
        "place_id": None,
        "display_name": None,
        "formatted_address": "",
        "latitude": None,
        "longitude": None,
        "country": None,
        "country_code": None,
        "region": None,
        "city": None,
        "district": None,
        "ward": None,
        "street": None,
        "postal_code": None,
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------- Nominatim

def _nominatim_headers() -> dict[str, str]:
    return {"User-Agent": settings.NOMINATIM_USER_AGENT, "Accept-Language": "en"}


def _nominatim_place_id(osm_type: str | None, osm_id: int | str | None) -> str:
    letter = {"node": "N", "way": "W", "relation": "R"}.get(str(osm_type), "N")
    return f"{letter}{osm_id}"


def _parse_nominatim_place_id(place_id: str) -> str:
    """Turn our encoded place id (N123/W123/R123) into a lookup osm_ids token."""
    if re.fullmatch(r"[NWR]\d+", place_id):
        return place_id
    raise MapServiceError("Unrecognised place reference — pick a search result again.")


def _first(*values: Any) -> Any:
    return next((v for v in values if v), None)


def _nominatim_address(item: dict[str, Any]) -> dict[str, Any]:
    addr = item.get("address") or {}
    house = addr.get("house_number")
    road = addr.get("road") or addr.get("pedestrian") or addr.get("path")
    street = f"{house} {road}".strip() if house and road else _first(road, item.get("name"))
    return _empty_location(
        place_id=_nominatim_place_id(item.get("osm_type"), item.get("osm_id")),
        display_name=item.get("display_name"),
        formatted_address=item.get("display_name") or "",
        latitude=item.get("lat"),
        longitude=item.get("lon"),
        country=addr.get("country"),
        country_code=addr.get("country_code"),
        region=_first(addr.get("state"), addr.get("region"), addr.get("province")),
        city=_first(addr.get("city"), addr.get("town"), addr.get("village"), addr.get("municipality")),
        district=_first(addr.get("city_district"), addr.get("district"), addr.get("county")),
        ward=_first(addr.get("suburb"), addr.get("neighbourhood"), addr.get("quarter")),
        street=street,
        postal_code=addr.get("postcode"),
    )


def _nominatim_autocomplete(query: str, country_code: str | None, language: str | None, limit: int) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": limit,
    }
    if country_code:
        params["countrycodes"] = country_code.lower()
    if language:
        params["accept-language"] = language

    headers = _nominatim_headers()
    if language:
        headers["Accept-Language"] = language
    data = _request(
        f"{settings.NOMINATIM_BASE_URL}{NOMINATIM_SEARCH_URL}", params, headers=headers
    )
    results = []
    for item in data or []:
        place_id = _nominatim_place_id(item.get("osm_type"), item.get("osm_id"))
        display = item.get("display_name") or ""
        main, _, secondary = display.partition(",")
        results.append(
            {
                "place_id": place_id,
                "description": display,
                "main_text": (item.get("name") or main).strip(),
                "secondary_text": secondary.strip() or None,
            }
        )
    return results


def _nominatim_place(place_id: str, language: str | None) -> dict[str, Any]:
    osm_ids = _parse_nominatim_place_id(place_id)
    headers = _nominatim_headers()
    if language:
        headers["Accept-Language"] = language
    data = _request(
        f"{settings.NOMINATIM_BASE_URL}{NOMINATIM_LOOKUP_URL}",
        {"osm_ids": osm_ids, "format": "jsonv2", "addressdetails": 1},
        headers=headers,
    )
    if not data:
        raise MapServiceError("Location not found — search again and pick a suggestion.")
    return _nominatim_address(data[0])


def _nominatim_reverse(latitude: float, longitude: float, language: str | None) -> dict[str, Any]:
    headers = _nominatim_headers()
    if language:
        headers["Accept-Language"] = language
    data = _request(
        f"{settings.NOMINATIM_BASE_URL}{NOMINATIM_REVERSE_URL}",
        {"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1, "zoom": 18},
        headers=headers,
    )
    if not data or data.get("error"):
        raise MapServiceError("Could not identify this location — try moving the pin slightly.")
    return _nominatim_address(data)


# -------------------------------------------------------------------- Google

_GOOGLE_COMPONENT_MAP = {
    "country": "country",
    "administrative_area_level_1": "region",
    "administrative_area_level_2": "district",
    "locality": "city",
    "postal_town": "city",
    "sublocality": "ward",
    "sublocality_level_1": "ward",
    "neighborhood": "ward",
    "route": "street",
    "postal_code": "postal_code",
}


def _google_address(result: dict[str, Any]) -> dict[str, Any]:
    components = result.get("address_components") or []
    fields: dict[str, str | None] = {}
    for comp in components:
        for comp_type in comp.get("types") or []:
            target = _GOOGLE_COMPONENT_MAP.get(comp_type)
            if target and target not in fields:
                fields[target] = comp.get("long_name")
            if comp_type == "country" and "country_code" not in fields:
                fields["country_code"] = comp.get("short_name")
            if comp_type == "street_number":
                fields["street_number"] = comp.get("long_name")

    street = fields.get("street")
    if fields.get("street_number") and street:
        street = f"{fields['street_number']} {street}"

    geometry = (result.get("geometry") or {}).get("location") or {}
    return _empty_location(
        place_id=result.get("place_id"),
        display_name=result.get("formatted_address"),
        formatted_address=result.get("formatted_address") or result.get("name") or "",
        latitude=geometry.get("lat"),
        longitude=geometry.get("lng"),
        country=fields.get("country"),
        country_code=fields.get("country_code"),
        region=fields.get("region"),
        city=fields.get("city"),
        district=fields.get("district"),
        ward=fields.get("ward"),
        street=street,
        postal_code=fields.get("postal_code"),
    )


def _google_check(payload: dict[str, Any]) -> dict[str, Any]:
    status = payload.get("status")
    if status in ("OK", "ZERO_RESULTS"):
        return payload
    raise MapServiceError(f"Google Maps returned {status}: {payload.get('error_message') or 'no detail'}")


def _google_autocomplete(query: str, country_code: str | None, language: str | None, limit: int, session_token: str | None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "input": query,
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    if country_code:
        params["components"] = f"country:{country_code.lower()}"
    if language:
        params["language"] = language
    if session_token:
        params["sessiontoken"] = session_token

    payload = _google_check(_request(GOOGLE_AUTOCOMPLETE_URL, params))
    results = []
    for item in (payload.get("predictions") or [])[:limit]:
        fmt = item.get("structured_formatting") or {}
        results.append(
            {
                "place_id": item.get("place_id"),
                "description": item.get("description") or "",
                "main_text": fmt.get("main_text"),
                "secondary_text": fmt.get("secondary_text"),
            }
        )
    return results


def _google_place(place_id: str, language: str | None, session_token: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "place_id": place_id,
        "fields": "place_id,name,formatted_address,geometry,address_components",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    if language:
        params["language"] = language
    if session_token:
        params["sessiontoken"] = session_token

    payload = _google_check(_request(GOOGLE_DETAILS_URL, params))
    result = payload.get("result")
    if not result:
        raise MapServiceError("Location not found — search again and pick a suggestion.")
    return _google_address(result)


def _google_reverse(latitude: float, longitude: float, language: str | None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "latlng": f"{latitude},{longitude}",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    if language:
        params["language"] = language

    payload = _google_check(_request(GOOGLE_GEOCODE_URL, params))
    results = payload.get("results") or []
    if not results:
        raise MapServiceError("Could not identify this location — try moving the pin slightly.")
    return _google_address(results[0])


# --------------------------------------------------------------- public API

def autocomplete(
    query: str,
    country_code: str | None = None,
    language: str | None = None,
    limit: int = 6,
    session_token: str | None = None,
) -> list[dict[str, Any]]:
    if active_provider() == "google":
        return _google_autocomplete(query, country_code, language, limit, session_token)
    return _nominatim_autocomplete(query, country_code, language, limit)


def place_details(
    place_id: str,
    language: str | None = None,
    region_code: str | None = None,
    session_token: str | None = None,
) -> dict[str, Any]:
    if active_provider() == "google" and not re.fullmatch(r"[NWR]\d+", place_id):
        return _google_place(place_id, language, session_token)
    return _nominatim_place(place_id, language)


def reverse_geocode(
    latitude: float,
    longitude: float,
    language: str | None = None,
) -> dict[str, Any]:
    if active_provider() == "google":
        return _google_reverse(latitude, longitude, language)
    return _nominatim_reverse(latitude, longitude, language)
