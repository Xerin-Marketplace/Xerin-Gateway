from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from api.middleware.audit import AuditMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.config import settings
from api.database import SessionLocal
from api.routers import (
    advertisements,
    analytics,
    audit_logs,
    admin,
    auth,
    cart,
    commissions,
    coupons,
    inventory,
    orders,
    payments,
    products,
    promotions,
    sellers,
    seller_orders,
    seller_inventory,
    delivery_integration,
    shipping,
    stores,
    storefront,
    users,
    wallets,
    refunds,
    reviews,
    wishlist,
    notifications,
    product_qa,
    search_recommendations,
    admin_dashboard,
    fulfilment,
    logistics,
    settings as settings_router,
    driver_kyc,
    delivery_fare,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):

    if settings.SERVE_LOCAL_UPLOADS:
        settings.upload_path.mkdir(parents=True, exist_ok=True)

    # Auto-seed permissions so new permissions are added to existing roles
    try:
        from api.seed_permissions import seed_permissions
        db = SessionLocal()
        seed_permissions(db)
        db.close()
        logger.info("Permissions seeded successfully")
    except Exception:
        logger.warning("Permission seeding skipped")

    logger.info(
        "Starting %s in %s mode",
        settings.APP_NAME,
        settings.APP_ENV,
    )
    yield
    logger.info("Stopping %s", settings.APP_NAME)


api = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

if settings.trusted_hosts:
    api.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["testserver", *settings.trusted_hosts],
)


api.add_middleware(AuditMiddleware)

api.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@api.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return JSON 500s so error responses still flow through CORSMiddleware.

    Without this handler, unhandled exceptions escape to Starlette's
    ServerErrorMiddleware — which sits *outside* CORSMiddleware — so the
    browser sees a 500 with no Access-Control-Allow-Origin header and
    reports it as a CORS failure, hiding the real error.
    """
    request_id = request.headers.get("X-Request-ID")
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            **({"request_id": request_id} if request_id else {}),
        },
    )


@api.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {
        "message": f"{settings.APP_NAME} is running",
        "environment": settings.APP_ENV,
    }


@api.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@api.get("/health/ready", tags=["system"])
def readiness() -> dict[str, str]:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Database readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    finally:
        db.close()

    return {"status": "ready", "database": "ok"}


if settings.SERVE_LOCAL_UPLOADS:
    api.mount(
        "/uploads",
        StaticFiles(directory=str(settings.upload_path)),
        name="uploads",
    )


for router in (
    advertisements.router,
    analytics.router,
    audit_logs.router,
    auth.router,
    users.router,
    sellers.router,
    seller_orders.router,
    seller_inventory.router,
    delivery_integration.router,
    products.router,
    promotions.router,
    cart.router,
    commissions.router,
    wallets.router,
    refunds.router,
    orders.router,
    payments.router,
    inventory.router,
    coupons.router,
    shipping.router,
    admin.router,
    stores.router,
    storefront.router,
    reviews.router,
    wishlist.router,
    notifications.router,
    product_qa.router,
    search_recommendations.router,
    admin_dashboard.router,
    fulfilment.router,
    logistics.router,
    settings_router.router,
    driver_kyc.router,
    delivery_fare.router,
):
    api.include_router(router, prefix=settings.API_PREFIX)
