"""Public advertisement slots.

The full campaign/advertising module is not present in this branch. These
endpoints return empty results so the storefront gracefully falls back to
platform content instead of logging 404s.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/advertisements", tags=["Advertisements"])


@router.get("/slots")
def public_slots() -> list:
    return []


@router.get("/active")
def public_active() -> list:
    return []
