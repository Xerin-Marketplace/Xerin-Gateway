from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode, SellerOrderStatus, ShipmentStatus
from api.models import LogisticsCompany, Order, SellerOrder, Shipment, ShipmentHandover, ShipmentTrackingEvent, User
from api.permissions import require_permission
from api.schemas import (
    SellerFulfillmentDashboardSummary,
    SellerFulfillmentDetailResponse,
    SellerFulfillmentListResponse,
    SellerFulfillmentTrackingListResponse,
)
from api.services.seller_fulfillment_readiness import evaluate_seller_fulfillment_readiness
from api.services.seller_fulfillment_view import (
    customer_name,
    detail_view,
    package_totals,
    seller_fulfillment_query,
    seller_handover,
    seller_shipment,
)


router = APIRouter(
    prefix="/seller/fulfillment",
    tags=["Seller Fulfillment"],
)


def _seller(user: User):
    if not user.seller_profile:
        raise HTTPException(403, "Seller profile required")
    return user.seller_profile


def _row(
    db: Session,
    *,
    seller_id: UUID,
    seller_order_id: UUID,
) -> SellerOrder:
    row = (
        seller_fulfillment_query(db, seller_id)
        .filter(SellerOrder.id == seller_order_id)
        .first()
    )
    if row is None:
        raise HTTPException(404, "Seller fulfillment order not found")
    return row


@router.get(
    "/summary",
    response_model=SellerFulfillmentDashboardSummary,
)
def fulfillment_summary(
    db: Session = Depends(get_db),
    user: User = Depends(
        require_permission(PermissionCode.seller_orders_read.value)
    ),
):
    seller = _seller(user)
    rows = (
        seller_fulfillment_query(db, seller.id)
        .order_by(SellerOrder.created_at.desc())
        .all()
    )

    result = {
        "total": len(rows),
        "new": 0,
        "processing": 0,
        "ready_to_ship": 0,
        "awaiting_courier": 0,
        "courier_arrived": 0,
        "seller_confirmed": 0,
        "shipped": 0,
        "delivered": 0,
        "blocked_readiness": 0,
    }

    for row in rows:
        status = getattr(row.status, "value", str(row.status))
        if status == "new":
            result["new"] += 1
        elif status in {"accepted", "processing"}:
            result["processing"] += 1
        elif status == "ready_to_ship":
            result["ready_to_ship"] += 1
        elif status == "shipped":
            result["shipped"] += 1
        elif status == "delivered":
            result["delivered"] += 1

        handover = seller_handover(db, seller_order_id=row.id)
        if handover:
            if handover.status == "awaiting_courier":
                result["awaiting_courier"] += 1
            elif handover.status == "courier_arrived":
                result["courier_arrived"] += 1
            elif handover.status == "seller_confirmed":
                result["seller_confirmed"] += 1

        if status in {"accepted", "processing"}:
            readiness = evaluate_seller_fulfillment_readiness(
                db,
                seller_order=row,
            )
            if not readiness.ready:
                result["blocked_readiness"] += 1

    return result


@router.get(
    "",
    response_model=SellerFulfillmentListResponse,
)
def list_fulfillment(
    search: str | None = Query(default=None, min_length=1, max_length=120),
    seller_status: SellerOrderStatus | None = Query(default=None),
    shipment_status: ShipmentStatus | None = Query(default=None),
    handover_status: str | None = Query(
        default=None,
        pattern="^(awaiting_courier|courier_arrived|seller_confirmed)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_permission(PermissionCode.seller_orders_read.value)
    ),
):
    seller = _seller(user)
    query = seller_fulfillment_query(db, seller.id)

    if seller_status is not None:
        query = query.filter(SellerOrder.status == seller_status)

    if search:
        token = f"%{search.strip()}%"
        query = (
            query.join(Order, SellerOrder.order_id == Order.id)
            .join(User, Order.user_id == User.id)
            .filter(
                or_(
                    cast(Order.id, String).ilike(token),
                    cast(SellerOrder.id, String).ilike(token),
                    Order.notes.ilike(token),
                    User.first_name.ilike(token),
                    User.last_name.ilike(token),
                    User.email.ilike(token),
                    User.phone.ilike(token),
                    db.query(Shipment.id)
                    .filter(
                        Shipment.order_id == SellerOrder.order_id,
                        Shipment.seller_id == SellerOrder.seller_id,
                        Shipment.store_id == SellerOrder.store_id,
                        Shipment.tracking_number.ilike(token),
                    )
                    .exists(),
                    db.query(Shipment.id)
                    .join(
                        LogisticsCompany,
                        LogisticsCompany.id == Shipment.logistics_company_id,
                    )
                    .filter(
                        Shipment.order_id == SellerOrder.order_id,
                        Shipment.seller_id == SellerOrder.seller_id,
                        Shipment.store_id == SellerOrder.store_id,
                        LogisticsCompany.name.ilike(token),
                    )
                    .exists(),
                )
            )
        )

    # Filters that belong to one-to-one seller shipment/handover records are
    # expressed using correlated EXISTS so count/pagination are not duplicated.
    if shipment_status is not None:
        query = query.filter(
            db.query(Shipment.id)
            .filter(
                Shipment.order_id == SellerOrder.order_id,
                Shipment.seller_id == SellerOrder.seller_id,
                Shipment.store_id == SellerOrder.store_id,
                Shipment.status == shipment_status,
            )
            .exists()
        )

    if handover_status is not None:
        query = query.filter(
            db.query(ShipmentHandover.id)
            .filter(
                ShipmentHandover.seller_order_id == SellerOrder.id,
                ShipmentHandover.status == handover_status,
            )
            .exists()
        )

    total = query.count()
    rows = (
        query.order_by(SellerOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    results = []
    for row in rows:
        packages = list(row.packages or [])
        totals = package_totals(packages)
        shipment = seller_shipment(row)
        handover = seller_handover(db, seller_order_id=row.id)
        readiness = evaluate_seller_fulfillment_readiness(
            db,
            seller_order=row,
        )
        company = shipment.logistics_company if shipment else None

        results.append(
            {
                "seller_order_id": row.id,
                "order_id": row.order_id,
                "store_id": row.store_id,
                "store_name": row.store.store_name if row.store else None,
                "store_country": row.store.country if row.store else None,
                "seller_status": row.status,
                "order_status": row.order.status,
                "customer_name": customer_name(row),
                "customer_phone": row.order.user.phone,
                "currency": row.order.currency,
                "seller_subtotal": row.seller_subtotal,
                "item_count": row.item_count,
                **totals,
                "shipment_id": shipment.id if shipment else None,
                "shipment_status": shipment.status if shipment else None,
                "logistics_company_id": (
                    shipment.logistics_company_id if shipment else None
                ),
                "logistics_company_name": company.name if company else None,
                "handover_status": handover.status if handover else None,
                "readiness_ready": readiness.ready,
                "readiness_blocker_count": len(readiness.blockers),
                "tracking_number": (
                    shipment.tracking_number if shipment else None
                ),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (
            (total + page_size - 1) // page_size
            if total
            else 0
        ),
        "results": results,
    }


@router.get(
    "/{seller_order_id}",
    response_model=SellerFulfillmentDetailResponse,
)
def fulfillment_detail(
    seller_order_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_permission(PermissionCode.seller_orders_read.value)
    ),
):
    seller = _seller(user)
    row = _row(
        db,
        seller_id=seller.id,
        seller_order_id=seller_order_id,
    )
    return detail_view(db, row)


@router.get(
    "/{seller_order_id}/tracking",
    response_model=SellerFulfillmentTrackingListResponse,
)
def fulfillment_tracking(
    seller_order_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(
        require_permission(PermissionCode.seller_orders_read.value)
    ),
):
    seller = _seller(user)
    row = _row(
        db,
        seller_id=seller.id,
        seller_order_id=seller_order_id,
    )
    shipment = seller_shipment(row)
    if shipment is None:
        return {
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "results": [],
        }

    query = db.query(ShipmentTrackingEvent).filter(
        ShipmentTrackingEvent.shipment_id == shipment.id
    )
    total = query.count()
    results = (
        query.order_by(ShipmentTrackingEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (
            (total + page_size - 1) // page_size
            if total
            else 0
        ),
        "results": results,
    }
