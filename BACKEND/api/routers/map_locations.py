from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from api.config import settings
from api.deps import get_current_user
from api.models import User
from api.schemas import MapAutocompleteResponse, MapProviderConfigResponse, MapResolvedLocation
from api.services.map_location_service import GoogleMapLocationClient, MapConfigurationError, MapProviderError

router = APIRouter(prefix="/locations/map", tags=["Map Locations"])

def _client() -> GoogleMapLocationClient:
    return GoogleMapLocationClient()

def _provider_error(exc: Exception) -> HTTPException:
    if isinstance(exc, MapConfigurationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Map/location service is not configured")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

@router.get("/config", response_model=MapProviderConfigResponse)
def map_provider_config(_: User = Depends(get_current_user)):
    return {"provider": "google", "enabled": bool((settings.GOOGLE_MAPS_API_KEY or "").strip()), "default_country_code": settings.MAP_DEFAULT_COUNTRY_CODE.upper(), "default_language": settings.MAP_DEFAULT_LANGUAGE}

@router.get("/autocomplete", response_model=MapAutocompleteResponse)
def map_autocomplete(query: str = Query(min_length=3, max_length=180), session_token: str | None = Query(default=None, min_length=8, max_length=180), country_code: str | None = Query(default=None, min_length=2, max_length=2), language: str | None = Query(default=None, min_length=2, max_length=12), limit: int = Query(default=8, ge=1, le=10), _: User = Depends(get_current_user)):
    clean_query = query.strip()
    if len(clean_query) < 3:
        raise HTTPException(status_code=422, detail="Search query must contain at least 3 characters")
    try:
        results = _client().autocomplete(query=clean_query, session_token=session_token, country_code=country_code, language=language, limit=limit)
    except (MapConfigurationError, MapProviderError) as exc:
        raise _provider_error(exc) from exc
    return {"provider": "google", "query": clean_query, "session_token": session_token, "results": results}

@router.get("/places/{place_id}", response_model=MapResolvedLocation)
def map_place_details(place_id: str, session_token: str | None = Query(default=None, min_length=8, max_length=180), language: str | None = Query(default=None, min_length=2, max_length=12), region_code: str | None = Query(default=None, min_length=2, max_length=2), _: User = Depends(get_current_user)):
    place_id = place_id.strip()
    if not place_id or len(place_id) > 255:
        raise HTTPException(status_code=422, detail="Invalid place_id")
    try:
        return _client().place_details(place_id=place_id, session_token=session_token, language=language, region_code=region_code)
    except (MapConfigurationError, MapProviderError) as exc:
        raise _provider_error(exc) from exc

@router.get("/reverse-geocode", response_model=MapResolvedLocation)
def map_reverse_geocode(latitude: Decimal = Query(ge=Decimal("-90"), le=Decimal("90")), longitude: Decimal = Query(ge=Decimal("-180"), le=Decimal("180")), language: str | None = Query(default=None, min_length=2, max_length=12), _: User = Depends(get_current_user)):
    try:
        return _client().reverse_geocode(latitude=latitude, longitude=longitude, language=language)
    except (MapConfigurationError, MapProviderError) as exc:
        raise _provider_error(exc) from exc
