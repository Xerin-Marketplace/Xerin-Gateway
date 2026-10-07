"""Location lookup endpoints shared by web checkout and the mobile app.

GET /locations/map/config          — whether map lookups are enabled + provider
GET /locations/map/autocomplete    — place suggestions
GET /locations/map/places/{id}     — resolve a suggestion into address parts
GET /locations/map/reverse-geocode — resolve lat/lng into address parts
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from api.services import map_service
from api.services.map_service import MapServiceError

router = APIRouter(prefix="/locations", tags=["Locations"])


class MapConfigResponse(BaseModel):
    enabled: bool
    provider: str


class MapAutocompleteSuggestion(BaseModel):
    place_id: str
    description: str
    main_text: str | None = None
    secondary_text: str | None = None


class MapAutocompleteResponse(BaseModel):
    results: list[MapAutocompleteSuggestion]


class MapResolvedLocation(BaseModel):
    provider: str
    place_id: str | None = None
    display_name: str | None = None
    formatted_address: str = ""
    latitude: Decimal | float | str | None = None
    longitude: Decimal | float | str | None = None
    country: str | None = None
    country_code: str | None = None
    region: str | None = None
    city: str | None = None
    district: str | None = None
    ward: str | None = None
    street: str | None = None
    postal_code: str | None = None


def _map_error(exc: MapServiceError) -> HTTPException:
    message = str(exc)
    lowered = message.lower()
    code = (
        status.HTTP_404_NOT_FOUND
        if "not found" in lowered or "unrecognised" in lowered
        else status.HTTP_502_BAD_GATEWAY
    )
    return HTTPException(status_code=code, detail=message)


@router.get("/map/config", response_model=MapConfigResponse)
def map_config() -> dict[str, Any]:
    return {"enabled": True, "provider": map_service.active_provider()}


@router.get("/map/autocomplete", response_model=MapAutocompleteResponse)
def map_autocomplete(
    query: str = Query(..., min_length=2, max_length=200),
    country_code: str | None = Query(None, min_length=2, max_length=2),
    language: str | None = Query(None, max_length=10),
    limit: int = Query(6, ge=1, le=10),
    session_token: str | None = Query(None, max_length=64),
    current_user=Depends(get_current_user),
):
    try:
        return {
            "results": map_service.autocomplete(
                query=query.strip(),
                country_code=country_code,
                language=language,
                limit=limit,
                session_token=session_token,
            )
        }
    except MapServiceError as exc:
        raise _map_error(exc) from exc


@router.get("/map/places/{place_id}", response_model=MapResolvedLocation)
def map_place_details(
    place_id: str,
    region_code: str | None = Query(None, max_length=10),
    language: str | None = Query(None, max_length=10),
    session_token: str | None = Query(None, max_length=64),
    current_user=Depends(get_current_user),
):
    try:
        return map_service.place_details(
            place_id=place_id,
            language=language,
            region_code=region_code,
            session_token=session_token,
        )
    except MapServiceError as exc:
        raise _map_error(exc) from exc


@router.get("/map/reverse-geocode", response_model=MapResolvedLocation)
def map_reverse_geocode(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    language: str | None = Query(None, max_length=10),
    current_user=Depends(get_current_user),
):
    try:
        return map_service.reverse_geocode(
            latitude=latitude, longitude=longitude, language=language
        )
    except MapServiceError as exc:
        raise _map_error(exc) from exc
