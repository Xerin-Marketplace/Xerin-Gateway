from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_current_user, get_db
from api.enums import PermissionCode, ShippingRateType, MultiSellerPricingStrategy
from api.models import (
    Address, Cart, CartItem, LogisticsCompany, MarketplaceSettings, Order,
    ProductStatus, Promotion, Shipment, ShipmentStatus, ShipmentTrackingEvent,
    ShippingMethod, ShippingRate, ShippingZone, User,
)
from api.permissions import require_permission
from api.services.multi_seller_pricing import (
    MultiSellerPricingError,
    calculate_multi_seller_delivery_pricing,
)
from api.services.delivery_quote import (
    DeliveryQuoteError,
    calculate_delivery_distance_quote,
)
from api.services.eligible_logistics import (
    EligibleLogisticsError,
    find_eligible_logistics_companies,
)
from api.schemas import (
    EligibleLogisticsSelectionRequest,
    DeliveryDistanceQuoteRequest,
    DeliveryDistanceQuoteResponse,
    MultiSellerDeliveryPricingRequest,
    MultiSellerDeliveryPricingResponse,
    PaginatedEligibleLogisticsCompanyResponse,
    ShippingMethodCreate, ShippingMethodResponse, ShippingMethodUpdate,
    ShippingCheckoutConfig, ShippingQuoteOption, ShippingQuoteRequest,
    ShippingRateCreate, ShippingRateResponse, ShippingZoneCreate,
    ShippingZoneResponse, ShippingZoneUpdate, ShipmentResponse,
    ShipmentTrackingEventCreate,
)

router = APIRouter(prefix="/shipping", tags=["Shipping"])

def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shipping record conflicts with existing data") from exc

@router.post("/zones", response_model=ShippingZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(data: ShippingZoneCreate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.shipping_write.value))):
    zone = ShippingZone(**data.model_dump())
    db.add(zone); _commit(db); db.refresh(zone); return zone

@router.get("/zones", response_model=list[ShippingZoneResponse])
def list_zones(active_only: bool = True, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q=db.query(ShippingZone)
    if active_only: q=q.filter(ShippingZone.is_active.is_(True))
    return q.order_by(ShippingZone.name).all()

@router.patch("/zones/{zone_id}", response_model=ShippingZoneResponse)
def update_zone(zone_id: UUID, data: ShippingZoneUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.shipping_write.value))):
    zone=db.get(ShippingZone, zone_id)
    if not zone: raise HTTPException(404, "Shipping zone not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(zone,k,v)
    _commit(db); db.refresh(zone); return zone

@router.post("/methods", response_model=ShippingMethodResponse, status_code=status.HTTP_201_CREATED)
def create_method(data: ShippingMethodCreate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.shipping_write.value))):
    if data.logistics_company_id and not db.get(LogisticsCompany, data.logistics_company_id):
        raise HTTPException(404, "Logistics company not found")
    method=ShippingMethod(**data.model_dump()); db.add(method); _commit(db); db.refresh(method); return method

@router.get("/methods", response_model=list[ShippingMethodResponse])
def list_methods(active_only: bool=True, db: Session=Depends(get_db), _: User=Depends(get_current_user)):
    q=db.query(ShippingMethod)
    if active_only: q=q.filter(ShippingMethod.is_active.is_(True))
    return q.order_by(ShippingMethod.name).all()

@router.post("/rates", response_model=ShippingRateResponse, status_code=status.HTTP_201_CREATED)
def create_rate(data: ShippingRateCreate, db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.shipping_write.value))):
    if not db.get(ShippingZone, data.zone_id): raise HTTPException(404, "Shipping zone not found")
    if not db.get(ShippingMethod, data.method_id): raise HTTPException(404, "Shipping method not found")
    rate=ShippingRate(**data.model_dump()); db.add(rate); _commit(db)
    return db.query(ShippingRate).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).filter(ShippingRate.id==rate.id).one()

@router.get("/rates", response_model=list[ShippingRateResponse])
def list_rates(db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.shipping_read.value))):
    return db.query(ShippingRate).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).order_by(ShippingRate.created_at.desc()).all()

def _normalise_country(value: str | None) -> str:
    return (value or "").strip().lower()


def _is_tanzania(value: str | None) -> bool:
    return _normalise_country(value) in {
        "tanzania",
        "united republic of tanzania",
        "tz",
    }


def _checkout_settings(db: Session) -> MarketplaceSettings | None:
    return (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.singleton_key == 1)
        .first()
    )


def _cart_shipping_facts(
    db: Session,
    user_id: UUID,
) -> tuple[Cart | None, Decimal, Decimal]:
    cart = (
        db.query(Cart)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product),
            selectinload(Cart.items).selectinload(CartItem.variant),
        )
        .filter(Cart.user_id == user_id)
        .first()
    )
    if not cart or not cart.items:
        return cart, Decimal("0.00"), Decimal("0.000")

    subtotal = Decimal("0.00")
    weight_kg = Decimal("0.000")

    for item in cart.items:
        product = item.product
        if (
            not product
            or not product.is_active
            or product.status != ProductStatus.approved
        ):
            continue

        subtotal += Decimal(item.unit_price) * item.quantity
        item_weight = (
            item.variant.weight
            if item.variant is not None and item.variant.weight is not None
            else product.weight
        )
        weight_kg += Decimal(item_weight or 0) * item.quantity

    return cart, subtotal, weight_kg


def _free_shipping_promotion_for_cart(
    db: Session,
    cart: Cart | None,
) -> Promotion | None:
    if not cart or not cart.promotion_code or not cart.items:
        return None

    now = datetime.now(timezone.utc)
    promotion = (
        db.query(Promotion)
        .options(selectinload(Promotion.rules))
        .filter(
            Promotion.code == cart.promotion_code,
            Promotion.promotion_type == "free_shipping",
            Promotion.is_active.is_(True),
            (Promotion.starts_at.is_(None) | (Promotion.starts_at <= now)),
            (Promotion.ends_at.is_(None) | (Promotion.ends_at >= now)),
        )
        .first()
    )
    if not promotion:
        return None

    for item in cart.items:
        product = item.product
        if not product:
            return None

        if promotion.seller_id is not None and product.seller_id != promotion.seller_id:
            return None

        target_rules = [
            rule
            for rule in promotion.rules
            if rule.rule_type in {"product", "category"}
        ]
        if target_rules:
            matched = any(
                (
                    rule.rule_type == "product"
                    and rule.product_id == product.id
                )
                or (
                    rule.rule_type == "category"
                    and rule.category_id == product.category_id
                )
                for rule in target_rules
            )
            if not matched:
                return None

    return promotion


@router.get("/checkout-config", response_model=ShippingCheckoutConfig)
def checkout_delivery_config(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings_row = _checkout_settings(db)
    return {
        "default_country": "Tanzania",
        "local_delivery_allowed": True,
        "international_delivery_allowed": bool(
            settings_row and settings_row.international_delivery_allowed
        ),
        "cod_allowed": bool(settings_row and settings_row.cod_allowed),
        "configured": bool(
            settings_row
            and settings_row.cod_allowed is not None
            and settings_row.international_delivery_allowed is not None
        ),
    }


@router.post(
    "/multi-seller-pricing",
    response_model=MultiSellerDeliveryPricingResponse,
)
def multi_seller_delivery_pricing(
    data: MultiSellerDeliveryPricingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return calculate_multi_seller_delivery_pricing(
            db,
            user_id=current_user.id,
            address_id=data.address_id,
            logistics_company_id=data.logistics_company_id,
            delivery_mode=data.delivery_mode,
            method_id=data.method_id,
        )
    except MultiSellerPricingError as exc:
        detail = {
            "code": exc.code,
            "message": exc.message,
        }
        detail.update(exc.extra)
        raise HTTPException(
            status_code=exc.status_code,
            detail=detail,
        ) from exc


@router.post(
    "/distance-quote",
    response_model=DeliveryDistanceQuoteResponse,
)
def delivery_distance_quote(
    data: DeliveryDistanceQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return calculate_delivery_distance_quote(
            db,
            user_id=current_user.id,
            address_id=data.address_id,
            logistics_company_id=data.logistics_company_id,
            delivery_mode=data.delivery_mode,
        )
    except DeliveryQuoteError as exc:
        detail = {
            "code": exc.code,
            "message": exc.message,
        }
        detail.update(exc.extra)
        raise HTTPException(
            status_code=exc.status_code,
            detail=detail,
        ) from exc


@router.post(
    "/eligible-logistics",
    response_model=PaginatedEligibleLogisticsCompanyResponse,
)
def eligible_logistics_companies(
    data: EligibleLogisticsSelectionRequest,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=150),
    supports_cod: bool | None = Query(default=None),
    supports_tracking: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return find_eligible_logistics_companies(
            db,
            user_id=current_user.id,
            address_id=data.address_id,
            delivery_mode=data.delivery_mode,
            page=page,
            page_size=page_size,
            search=search,
            supports_cod=supports_cod,
            supports_tracking=supports_tracking,
        )
    except EligibleLogisticsError as exc:
        detail = {
            "code": exc.code,
            "message": exc.message,
        }
        detail.update(exc.extra)
        raise HTTPException(
            status_code=exc.status_code,
            detail=detail,
        ) from exc


@router.post("/quote", response_model=list[ShippingQuoteOption])
def quote_shipping(
    data: ShippingQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(
            Address.id == data.address_id,
            Address.user_id == current_user.id,
        )
        .first()
    )
    if not address:
        raise HTTPException(404, "Address not found")

    settings_row = _checkout_settings(db)
    address_is_local = _is_tanzania(address.country)

    if data.delivery_mode == "local" and not address_is_local:
        raise HTTPException(
            status_code=422,
            detail="Local delivery requires a Tanzania delivery address",
        )

    if data.delivery_mode == "international" and address_is_local:
        raise HTTPException(
            status_code=422,
            detail="International delivery requires a non-Tanzania delivery address",
        )

    if data.delivery_mode == "international" and not (
        settings_row and settings_row.international_delivery_allowed
    ):
        raise HTTPException(
            status_code=409,
            detail="International delivery is not enabled for the marketplace",
        )

    cart, cart_subtotal, cart_weight_kg = _cart_shipping_facts(
        db,
        current_user.id,
    )
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    free_shipping_promotion = _free_shipping_promotion_for_cart(db, cart)

    country = (address.country or "").strip()
    requested_scope = data.delivery_mode

    zones = (
        db.query(ShippingZone)
        .filter(
            ShippingZone.is_active.is_(True),
            ShippingZone.country.ilike(country),
        )
        .all()
    )

    matching_zone_ids = []
    for zone in zones:
        zone_scope = (
            zone.scope.value
            if hasattr(zone.scope, "value")
            else str(zone.scope)
        )
        if requested_scope == "local" and zone_scope not in {"local", "both"}:
            continue
        if (
            requested_scope == "international"
            and zone_scope not in {"international", "both"}
        ):
            continue

        regions = {
            str(x).strip().lower()
            for x in (zone.regions or [])
        }
        cities = {
            str(x).strip().lower()
            for x in (zone.cities or [])
        }

        address_region = (address.region or "").strip().lower()
        address_city = (address.city or "").strip().lower()

        if regions and address_region not in regions:
            continue
        if cities and address_city not in cities:
            continue

        matching_zone_ids.append(zone.id)

    if not matching_zone_ids:
        return []

    query = (
        db.query(ShippingRate)
        .options(
            joinedload(ShippingRate.method)
            .joinedload(ShippingMethod.logistics_company)
        )
        .filter(
            ShippingRate.zone_id.in_(matching_zone_ids),
            ShippingRate.is_active.is_(True),
        )
    )

    if data.method_id is not None:
        query = query.filter(ShippingRate.method_id == data.method_id)

    rates = query.all()
    options = []

    for rate in rates:
        method = rate.method
        if not method or not method.is_active:
            continue

        method_scope = (
            method.scope.value
            if hasattr(method.scope, "value")
            else str(method.scope)
        )
        if requested_scope == "local" and method_scope not in {"local", "both"}:
            continue
        if (
            requested_scope == "international"
            and method_scope not in {"international", "both"}
        ):
            continue

        company = method.logistics_company
        if company:
            company_status = (
                company.status.value
                if hasattr(company.status, "value")
                else str(company.status)
            )
            if company_status != "active":
                continue

            if (
                data.logistics_company_id is not None
                and company.id != data.logistics_company_id
            ):
                continue
        elif data.logistics_company_id is not None:
            continue

        if (
            rate.min_weight_kg is not None
            and cart_weight_kg < Decimal(rate.min_weight_kg)
        ):
            continue
        if (
            rate.max_weight_kg is not None
            and cart_weight_kg > Decimal(rate.max_weight_kg)
        ):
            continue

        if (
            rate.free_shipping_threshold is not None
            and cart_subtotal >= Decimal(rate.free_shipping_threshold)
        ):
            original_amount = Decimal("0.00")
        elif rate.rate_type == ShippingRateType.free:
            original_amount = Decimal("0.00")
        elif rate.rate_type == ShippingRateType.weight_based:
            original_amount = (
                Decimal(rate.base_amount)
                + Decimal(rate.amount_per_kg) * cart_weight_kg
            )
        else:
            original_amount = Decimal(rate.base_amount)

        original_amount = original_amount.quantize(Decimal("0.01"))
        promotion_discount = (
            original_amount if free_shipping_promotion else Decimal("0.00")
        )
        final_amount = max(
            Decimal("0.00"),
            original_amount - promotion_discount,
        ).quantize(Decimal("0.01"))

        supports_cod = bool(
            requested_scope == "local"
            and settings_row
            and settings_row.cod_allowed
            and method.supports_cod
            and (company.supports_cod if company else True)
        )

        options.append(
            ShippingQuoteOption(
                rate_id=rate.id,
                method_id=method.id,
                logistics_company_id=company.id if company else None,
                logistics_company_name=(
                    company.name if company else method.carrier_name
                ),
                method_name=method.name,
                carrier_name=(
                    method.carrier_name
                    or (company.name if company else None)
                ),
                scope=method.scope,
                supports_cod=supports_cod,
                supports_tracking=(
                    method.supports_tracking
                    and bool(
                        company.supports_tracking
                        if company
                        else True
                    )
                ),
                original_amount=original_amount,
                shipping_discount_amount=promotion_discount,
                amount=final_amount,
                currency=rate.currency,
                min_delivery_days=method.min_delivery_days,
                max_delivery_days=method.max_delivery_days,
                free_shipping_applied=bool(free_shipping_promotion),
                promotion_code=(
                    free_shipping_promotion.code
                    if free_shipping_promotion
                    else None
                ),
                promotion_name=(
                    free_shipping_promotion.name
                    if free_shipping_promotion
                    else None
                ),
            )
        )

    return sorted(
        options,
        key=lambda item: (
            item.logistics_company_name or "",
            item.currency,
            item.amount,
        ),
    )


ALLOWED_SHIPMENT_TRANSITIONS = {
    ShipmentStatus.pending: {ShipmentStatus.ready_for_dispatch, ShipmentStatus.cancelled},
    ShipmentStatus.ready_for_dispatch: {ShipmentStatus.dispatched, ShipmentStatus.cancelled},
    ShipmentStatus.dispatched: {ShipmentStatus.in_transit, ShipmentStatus.delivery_failed},
    ShipmentStatus.in_transit: {ShipmentStatus.out_for_delivery, ShipmentStatus.delivery_failed, ShipmentStatus.returned_to_sender},
    ShipmentStatus.out_for_delivery: {ShipmentStatus.delivered, ShipmentStatus.delivery_failed, ShipmentStatus.returned_to_sender},
    ShipmentStatus.delivery_failed: {ShipmentStatus.out_for_delivery, ShipmentStatus.returned_to_sender},
    ShipmentStatus.delivered: set(),
    ShipmentStatus.returned_to_sender: set(),
    ShipmentStatus.cancelled: set(),
}


def _can_manage_shipment(db: Session, user: User, shipment: Shipment) -> bool:
    from api.permissions import get_user_permissions, get_user_role_names
    roles = get_user_role_names(user)
    permissions = get_user_permissions(db, user)
    if "super_admin" in roles or PermissionCode.shipping_manage_all.value in permissions:
        return True
    return bool(user.seller_profile and user.seller_profile.id == shipment.seller_id and PermissionCode.shipping_manage_own.value in permissions)


def _can_view_shipment(db: Session, user: User, shipment: Shipment) -> bool:
    return shipment.order.user_id == user.id or _can_manage_shipment(db, user, shipment) or PermissionCode.shipping_read.value in __import__('api.permissions', fromlist=['get_user_permissions']).get_user_permissions(db, user)


@router.get("/shipments/my", response_model=list[ShipmentResponse])
def my_shipments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events)).join(Order).filter(Order.user_id == current_user.id).order_by(Shipment.created_at.desc()).all()


@router.get("/shipments/seller", response_model=list[ShipmentResponse])
def seller_shipments(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.shipping_manage_own.value))):
    if not current_user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    return db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events)).filter(Shipment.seller_id == current_user.seller_profile.id).order_by(Shipment.created_at.desc()).all()


@router.get("/shipments/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    shipment = db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events), joinedload(Shipment.order)).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not _can_view_shipment(db, current_user, shipment):
        raise HTTPException(status_code=403, detail="Not authorized to view this shipment")
    return shipment


@router.post("/shipments/{shipment_id}/events", response_model=ShipmentResponse)
def update_shipment(shipment_id: UUID, data: ShipmentTrackingEventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    shipment = db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events), joinedload(Shipment.order)).filter(Shipment.id == shipment_id).with_for_update().first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not _can_manage_shipment(db, current_user, shipment):
        raise HTTPException(status_code=403, detail="Not authorized to manage this shipment")
    if data.status not in ALLOWED_SHIPMENT_TRANSITIONS.get(shipment.status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid shipment transition: {shipment.status.value} -> {data.status.value}")
    if data.tracking_number:
        duplicate = db.query(Shipment.id).filter(Shipment.tracking_number == data.tracking_number, Shipment.id != shipment.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Tracking number is already in use")
        shipment.tracking_number = data.tracking_number.strip()
    if data.carrier_name:
        shipment.carrier_name = data.carrier_name.strip()
    shipment.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == ShipmentStatus.dispatched and shipment.dispatched_at is None:
        shipment.dispatched_at = now
    if data.status == ShipmentStatus.delivered:
        shipment.delivered_at = now
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id, status=data.status, location=data.location, notes=data.notes, created_by_id=current_user.id))
    _commit(db)
    return db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events)).filter(Shipment.id == shipment.id).one()
