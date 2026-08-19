from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from api.config import settings
from api.deps import get_current_user, get_db
from api.permissions import require_permission
from api.enums import DeliveryStatus, PermissionCode, SellerOrderStatus, ShipmentStatus
from api.models import (
    DeliveryJob,
    Order,
    Seller,
    SellerPickupLocation,
    SellerOrder,
    Shipment,
    ShipmentTrackingEvent,
    User,
)
from api.schemas import DeliveryQuoteRequest, DeliveryQuoteResponse, DeliveryRequestResponse, DeliveryWebhookResponse

router = APIRouter(prefix="/delivery", tags=["External Delivery Integration"])


def _seller(user: User) -> Seller:
    seller = getattr(user, "seller_profile", None)
    if not seller:
        raise HTTPException(403, "Seller profile is required")
    return seller


def _provider_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if settings.DELIVERY_API_KEY:
        headers[settings.DELIVERY_API_KEY_HEADER] = settings.DELIVERY_API_KEY
    return headers


def _provider_post(path: str, payload: dict) -> dict:
    if not settings.DELIVERY_API_BASE_URL:
        raise HTTPException(503, "External delivery provider is not configured")
    url = f"{settings.DELIVERY_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = requests.post(url, json=payload, headers=_provider_headers(), timeout=settings.DELIVERY_API_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise HTTPException(502, f"Delivery provider request failed: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(502, "Delivery provider returned invalid JSON") from exc


def _pickup_payload(seller: Seller) -> dict:
    # Phase 1 logistics foundation: prefer the seller's active default pickup
    # point, including GPS. Fall back to the legacy business profile so existing
    # sellers continue to work until Task 3 makes pickup setup mandatory.
    pickup = next(
        (location for location in seller.pickup_locations if location.is_default and location.is_active),
        None,
    )
    if pickup is not None:
        return {
            "name": pickup.pickup_contact_name or seller.business_name,
            "phone": pickup.pickup_phone,
            "email": seller.contact_email or seller.user.email,
            "country": pickup.country,
            "region": pickup.region,
            "city": pickup.city,
            "district": pickup.district,
            "ward": pickup.ward,
            "address": pickup.formatted_address,
            "landmark": pickup.landmark,
            "latitude": float(pickup.latitude),
            "longitude": float(pickup.longitude),
            "pickup_location_id": str(pickup.id),
        }

    profile = seller.profile
    if not profile or not profile.business_address or not profile.business_city or not profile.business_region:
        raise HTTPException(409, "Complete the seller pickup address before requesting delivery")
    phone = seller.contact_phone or seller.user.phone
    if not phone:
        raise HTTPException(409, "Seller pickup phone number is required")
    return {
        "name": seller.business_name,
        "phone": phone,
        "email": seller.contact_email or seller.user.email,
        "country": profile.business_country or "Tanzania",
        "region": profile.business_region,
        "city": profile.business_city,
        "address": profile.business_address,
    }


def _dropoff_payload(order: Order) -> dict:
    address = order.shipping_address
    if not address:
        raise HTTPException(409, "Customer shipping address is missing")
    return {
        "name": address.recipient_name or f"{order.user.first_name or ''} {order.user.last_name or ''}".strip(),
        "phone": address.recipient_phone or order.user.phone,
        "country": address.country,
        "region": address.region,
        "district": address.district,
        "ward": address.ward,
        "city": address.city,
        "address": address.street,
        "landmark": address.landmark,
        "postal_code": address.postal_code,
        "latitude": float(address.latitude) if address.latitude is not None else None,
        "longitude": float(address.longitude) if address.longitude is not None else None,
    }


def _as_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _verify_signature(raw_body: bytes, supplied: str | None) -> None:
    secret = settings.DELIVERY_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(503, "Delivery webhook secret is not configured")
    if not supplied:
        raise HTTPException(401, "Missing delivery webhook signature")
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    normalized = supplied.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, normalized):
        raise HTTPException(401, "Invalid delivery webhook signature")


STATUS_MAP = {
    DeliveryStatus.created: ShipmentStatus.ready_for_dispatch,
    DeliveryStatus.awaiting_pickup: ShipmentStatus.ready_for_dispatch,
    DeliveryStatus.courier_assigned: ShipmentStatus.ready_for_dispatch,
    DeliveryStatus.picked_up: ShipmentStatus.dispatched,
    DeliveryStatus.in_transit: ShipmentStatus.in_transit,
    DeliveryStatus.out_for_delivery: ShipmentStatus.out_for_delivery,
    DeliveryStatus.delivered: ShipmentStatus.delivered,
    DeliveryStatus.delivery_failed: ShipmentStatus.delivery_failed,
    DeliveryStatus.cancelled: ShipmentStatus.cancelled,
    DeliveryStatus.returned: ShipmentStatus.returned_to_sender,
}


@router.post("/quote", response_model=DeliveryQuoteResponse)
def quote_delivery(data: DeliveryQuoteRequest, user: User = Depends(get_current_user)):
    response = _provider_post(settings.DELIVERY_QUOTE_PATH, data.model_dump(mode="json"))
    amount = response.get("fee", response.get("amount"))
    if amount is None:
        raise HTTPException(502, "Delivery provider response did not include a fee")
    return {
        "provider": settings.DELIVERY_PROVIDER_NAME,
        "quote_id": response.get("quote_id") or response.get("id"),
        "fee": Decimal(str(amount)),
        "currency": response.get("currency", data.currency),
        "estimated_pickup_at": response.get("estimated_pickup_at"),
        "estimated_delivery_at": response.get("estimated_delivery_at"),
        "raw_response": response,
    }


@router.get("/seller-orders/{seller_order_id}", response_model=DeliveryRequestResponse)
def get_delivery(
    seller_order_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PermissionCode.seller_delivery_read.value)),
):
    seller = _seller(user)
    job = (
        db.query(DeliveryJob)
        .join(SellerOrder, DeliveryJob.seller_order_id == SellerOrder.id)
        .filter(DeliveryJob.seller_order_id == seller_order_id, SellerOrder.seller_id == seller.id)
        .first()
    )
    if not job:
        raise HTTPException(404, "Delivery request not found")
    return job


@router.post("/seller-orders/{seller_order_id}/request", response_model=DeliveryRequestResponse)
def request_delivery(
    seller_order_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(PermissionCode.seller_delivery_request.value)),
):
    seller = _seller(user)
    row = (
        db.query(SellerOrder)
        .options(joinedload(SellerOrder.order).joinedload(Order.items), joinedload(SellerOrder.order).joinedload(Order.shipping_address), joinedload(SellerOrder.order).joinedload(Order.user))
        .filter(SellerOrder.id == seller_order_id, SellerOrder.seller_id == seller.id)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(404, "Seller order not found")
    if row.status != SellerOrderStatus.ready_to_ship:
        raise HTTPException(409, "Seller order must be ready to ship before delivery is requested")
    shipment = db.query(Shipment).filter(Shipment.order_id == row.order_id, Shipment.seller_id == seller.id).first()
    if not shipment:
        raise HTTPException(409, "Shipment has not been created")
    existing = db.query(DeliveryJob).filter(DeliveryJob.shipment_id == shipment.id).first()
    if existing and existing.status not in {DeliveryStatus.cancelled, DeliveryStatus.delivery_failed, DeliveryStatus.returned}:
        raise HTTPException(409, "An active delivery request already exists for this shipment")

    items = [item for item in row.order.items if item.seller_id == seller.id]
    payload = {
        "order_reference": str(row.order_id),
        "seller_order_reference": str(row.id),
        "pickup": _pickup_payload(seller),
        "dropoff": _dropoff_payload(row.order),
        "package": {
            "item_count": sum(item.quantity for item in items),
            "description": ", ".join(item.product_name for item in items)[:500],
            "declared_value": str(row.seller_subtotal),
            "currency": row.order.currency,
        },
        "callback_url": f"{settings.PUBLIC_BASE_URL.rstrip('/')}{settings.API_PREFIX}/delivery/webhooks/{settings.DELIVERY_PROVIDER_NAME}" if settings.PUBLIC_BASE_URL else None,
    }
    response = _provider_post(settings.DELIVERY_CREATE_PATH, payload)
    external_id = response.get("delivery_id") or response.get("id")
    if not external_id:
        raise HTTPException(502, "Delivery provider response did not include a delivery ID")

    job = existing or DeliveryJob(shipment_id=shipment.id, seller_order_id=row.id, provider=settings.DELIVERY_PROVIDER_NAME)
    job.external_delivery_id = str(external_id)
    job.status = DeliveryStatus.created
    job.tracking_number = response.get("tracking_number")
    job.tracking_url = response.get("tracking_url")
    job.delivery_fee = Decimal(str(response["delivery_fee"])) if response.get("delivery_fee") is not None else None
    job.currency = response.get("currency", row.order.currency)
    job.courier_name = response.get("courier_name")
    job.courier_phone = response.get("courier_phone")
    job.estimated_pickup_at = _as_datetime(response.get("estimated_pickup_at"))
    job.estimated_delivery_at = _as_datetime(response.get("estimated_delivery_at"))
    job.request_payload = payload
    job.provider_response = response
    job.last_synced_at = datetime.now(timezone.utc)
    db.add(job)
    shipment.carrier_name = settings.DELIVERY_PROVIDER_NAME
    shipment.tracking_number = job.tracking_number or shipment.tracking_number
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id, status=ShipmentStatus.ready_for_dispatch, notes="Delivery request sent to external provider", created_by_id=user.id))
    db.commit()
    db.refresh(job)
    return job


@router.post("/webhooks/{provider}", response_model=DeliveryWebhookResponse)
async def delivery_webhook(
    provider: str,
    request: Request,
    x_delivery_signature: str | None = Header(None),
    db: Session = Depends(get_db),
):
    if provider.lower() != settings.DELIVERY_PROVIDER_NAME.lower():
        raise HTTPException(404, "Unknown delivery provider")
    raw = await request.body()
    _verify_signature(raw, x_delivery_signature)
    try:
        payload = json.loads(raw)
        external_id = str(payload.get("delivery_id") or payload.get("id") or "")
        status = DeliveryStatus(str(payload.get("status")))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Invalid delivery webhook payload") from exc
    if not external_id:
        raise HTTPException(422, "delivery_id is required")
    job = db.query(DeliveryJob).filter(DeliveryJob.provider == settings.DELIVERY_PROVIDER_NAME, DeliveryJob.external_delivery_id == external_id).with_for_update().first()
    if not job:
        raise HTTPException(404, "Delivery request not found")

    now = datetime.now(timezone.utc)
    job.status = status
    job.tracking_number = payload.get("tracking_number") or job.tracking_number
    job.tracking_url = payload.get("tracking_url") or job.tracking_url
    job.courier_name = payload.get("courier_name") or job.courier_name
    job.courier_phone = payload.get("courier_phone") or job.courier_phone
    job.failure_reason = payload.get("failure_reason") or job.failure_reason
    job.provider_response = payload
    job.last_synced_at = now

    shipment = db.query(Shipment).filter(Shipment.id == job.shipment_id).first()
    shipment.status = STATUS_MAP[status]
    shipment.tracking_number = job.tracking_number or shipment.tracking_number
    shipment.carrier_name = settings.DELIVERY_PROVIDER_NAME
    if status == DeliveryStatus.picked_up and not shipment.dispatched_at:
        shipment.dispatched_at = now
    if status == DeliveryStatus.delivered:
        shipment.delivered_at = now
        seller_order = db.query(SellerOrder).filter(SellerOrder.id == job.seller_order_id).first()
        if seller_order:
            seller_order.status = SellerOrderStatus.delivered
            seller_order.delivered_at = now
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id, status=shipment.status, location=payload.get("location"), notes=payload.get("notes") or f"External delivery status: {status.value}"))
    db.commit()
    return {"accepted": True, "delivery_id": external_id, "status": status}
