from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from api.middleware.audit import AuditMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from api.config import settings
from api.database import SessionLocal
from api.routers import (
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
        allowed_hosts=[
        "127.0.0.1",
        "testserver",
        "localhost",
        "api.xerinmarketplace.com",
        "169.58.54.110",
    ],
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
):
    api.include_router(router, prefix=settings.API_PREFIX)
