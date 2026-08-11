from __future__ import annotations

import datetime
import secrets
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_current_user, get_db
from api.enums import (
    DeliveryTripStatus,
    DriverStatus,
    DriverVerificationStatus,
    NotificationChannel,
    NotificationEvent,
    PermissionCode,
    SellerOrderStatus,
    ShipmentStatus,
    StockTransferStatus,
    VehicleType,
)
from api.models import (
    Address,
    DeliveryTrip,
    DeliveryTripCoordinate,
    DeliveryTripEvent,
    DeliveryTripFee,
    Driver,
    Order,
    Product,
    Seller,
    SellerOrder,
    SellerStockTransfer,
    SellerStockTransferItem,
    Shipment,
    User,
    Vehicle,
    Warehouse,
    WarehouseInventory,
)
from api.permissions import require_permission
from api.services.notification_service import notification_service
from api.services.delivery_fare_service import calculate_fare
from api.schemas import FareCalculationRequest
from api.schemas import (
    AssignDriverRequest,
    DriverCreate,
    DriverListResponse,
    DriverLocationUpdate,
    DriverResponse,
    DriverUpdate,
    DeliveryTripListResponse,
    DeliveryTripResponse,
    ReceiveStockTransferRequest,
    StockTransferCreate,
    StockTransferListResponse,
    StockTransferResponse,
    StockTransferStatusUpdate,
    UpdateTripStatusRequest,
    VehicleCreate,
    VehicleListResponse,
    VehicleResponse,
    VehicleUpdate,
)

router = APIRouter(prefix="/logistics", tags=["Logistics"])


# =========================================================
# HELPERS
# =========================================================

def _driver_to_response(d: Driver, db: Session) -> DriverResponse:
    user = db.query(User).filter(User.id == d.user_id).first()
    vehicle = None
    if d.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == d.vehicle_id).first()
    return DriverResponse(
        id=d.id,
        user_id=d.user_id,
        license_number=d.license_number,
        license_expiry=d.license_expiry,
        national_id=d.national_id,
        profile_image_url=d.profile_image_url,
        phone=d.phone,
        emergency_contact=d.emergency_contact,
        status=d.status,
        verification_status=d.verification_status,
        is_online=d.is_online,
        rating=d.rating,
        total_deliveries=d.total_deliveries,
        total_ratings=d.total_ratings,
        current_latitude=d.current_latitude,
        current_longitude=d.current_longitude,
        last_location_at=d.last_location_at,
        service_zones=d.service_zones or [],
        vehicle_id=d.vehicle_id,
        approved_at=d.approved_at,
        suspended_at=d.suspended_at,
        suspend_reason=d.suspend_reason,
        created_at=d.created_at,
        updated_at=d.updated_at,
        user_name=f"{user.first_name} {user.last_name}" if user else None,
        user_email=user.email if user else None,
        vehicle_plate=vehicle.plate_number if vehicle else None,
        kyc_verified=d.kyc.is_verified if d.kyc else None,
        kyc_submitted=d.kyc is not None,
    )


def _vehicle_to_response(v: Vehicle) -> VehicleResponse:
    return VehicleResponse(
        id=v.id,
        plate_number=v.plate_number,
        vehicle_type=v.vehicle_type,
        brand=v.brand,
        model=v.model,
        year=v.year,
        color=v.color,
        capacity_kg=v.capacity_kg,
        volume_m3=v.volume_m3,
        license_expiry=v.license_expiry,
        insurance_expiry=v.insurance_expiry,
        is_active=v.is_active,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


def _trip_to_response(t: DeliveryTrip, db: Session) -> DeliveryTripResponse:
    driver = None
    if t.driver_id:
        driver = db.query(Driver).filter(Driver.id == t.driver_id).first()
    vehicle = None
    if t.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == t.vehicle_id).first()
    seller_order = db.query(SellerOrder).filter(SellerOrder.id == t.seller_order_id).first()
    order = None
    if seller_order:
        order = db.query(Order).filter(Order.id == seller_order.order_id).first()
    user = None
    if driver:
        user = db.query(User).filter(User.id == driver.user_id).first()
    return DeliveryTripResponse(
        id=t.id,
        ref_code=t.ref_code,
        shipment_id=t.shipment_id,
        seller_order_id=t.seller_order_id,
        driver_id=t.driver_id,
        vehicle_id=t.vehicle_id,
        status=t.status,
        pickup_address=t.pickup_address,
        delivery_address=t.delivery_address,
        estimated_distance_km=t.estimated_distance_km,
        estimated_duration_min=t.estimated_duration_min,
        delivery_fee=t.delivery_fee,
        currency=t.currency,
        otp=t.otp,
        pickup_at=t.pickup_at,
        delivered_at=t.delivered_at,
        failed_at=t.failed_at,
        failure_reason=t.failure_reason,
        notes=t.notes,
        created_at=t.created_at,
        updated_at=t.updated_at,
        driver_name=f"{user.first_name} {user.last_name}" if user else None,
        driver_phone=driver.phone if driver else None,
        vehicle_plate=vehicle.plate_number if vehicle else None,
        order_number=order.order_number if order else None,
    )


def _generate_ref_code(prefix: str = "DT") -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%y%m%d")
    rand = secrets.token_hex(3).upper()
    return f"{prefix}-{ts}-{rand}"


def _generate_transfer_ref() -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%y%m%d")
    rand = secrets.token_hex(3).upper()
    return f"ST-{ts}-{rand}"


def _get_seller_from_user(db: Session, user: User) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == user.id).first()
    if not seller:
        raise HTTPException(404, "Seller profile not found")
    return seller


def _transfer_to_response(t: SellerStockTransfer, db: Session) -> StockTransferResponse:
    warehouse = db.query(Warehouse).filter(Warehouse.id == t.warehouse_id).first()
    seller = db.query(Seller).filter(Seller.id == t.seller_id).first()
    items = []
    for item in t.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "variant_id": item.variant_id,
            "expected_quantity": item.expected_quantity,
            "received_quantity": item.received_quantity,
            "condition": item.condition,
            "notes": item.notes,
            "product_name": product.name if product else None,
        })
    return StockTransferResponse(
        id=t.id,
        reference=t.reference,
        seller_id=t.seller_id,
        warehouse_id=t.warehouse_id,
        status=t.status,
        origin_type=t.origin_type,
        origin_address=t.origin_address,
        expected_arrival_at=t.expected_arrival_at,
        dispatched_at=t.dispatched_at,
        received_at=t.received_at,
        transport_cost=t.transport_cost,
        currency=t.currency,
        notes=t.notes,
        rejection_reason=t.rejection_reason,
        created_at=t.created_at,
        updated_at=t.updated_at,
        warehouse_name=warehouse.name if warehouse else None,
        seller_name=seller.business_name if seller else None,
        items=items,
    )


# =========================================================
# DRIVER ENDPOINTS
# =========================================================

@router.get("/drivers", response_model=DriverListResponse)
def list_drivers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: DriverStatus | None = Query(None, alias="status"),
    verification: DriverVerificationStatus | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Driver)
    if status_filter:
        q = q.filter(Driver.status == status_filter)
    if verification:
        q = q.filter(Driver.verification_status == verification)
    if search:
        q = q.join(User, Driver.user_id == User.id).filter(
            or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                Driver.phone.ilike(f"%{search}%"),
                Driver.license_number.ilike(f"%{search}%"),
            )
        )
    total = q.count()
    drivers = q.order_by(Driver.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return DriverListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[_driver_to_response(d, db) for d in drivers],
    )


@router.get("/drivers/{driver_id}", response_model=DriverResponse)
def get_driver(
    driver_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return _driver_to_response(driver, db)


@router.post("/drivers", response_model=DriverResponse, status_code=201)
def create_driver(
    data: DriverCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_driver_manage)),
):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    existing = db.query(Driver).filter(Driver.user_id == data.user_id).first()
    if existing:
        raise HTTPException(409, "Driver profile already exists for this user")
    if data.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).first()
        if not vehicle:
            raise HTTPException(404, "Vehicle not found")
    driver = Driver(
        user_id=data.user_id,
        license_number=data.license_number,
        license_expiry=data.license_expiry,
        national_id=data.national_id,
        phone=data.phone,
        emergency_contact=data.emergency_contact,
        service_zones=data.service_zones,
        vehicle_id=data.vehicle_id,
        status=DriverStatus.offline,
        verification_status=DriverVerificationStatus.pending,
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return _driver_to_response(driver, db)


@router.put("/drivers/{driver_id}", response_model=DriverResponse)
def update_driver(
    driver_id: UUID,
    data: DriverUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_driver_manage)),
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(driver, field, value)
    if data.status == DriverStatus.suspended and not driver.suspended_at:
        driver.suspended_at = datetime.datetime.now(datetime.timezone.utc)
    elif data.status and data.status != DriverStatus.suspended:
        driver.suspended_at = None
        driver.suspend_reason = None
    db.commit()
    db.refresh(driver)
    return _driver_to_response(driver, db)


@router.post("/drivers/{driver_id}/approve", response_model=DriverResponse)
def approve_driver(
    driver_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_driver_manage)),
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.verification_status = DriverVerificationStatus.verified
    driver.approved_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(driver)
    return _driver_to_response(driver, db)


@router.post("/drivers/{driver_id}/suspend", response_model=DriverResponse)
def suspend_driver(
    driver_id: UUID,
    reason: str = Query(..., min_length=3),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_driver_manage)),
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.status = DriverStatus.suspended
    driver.suspended_at = datetime.datetime.now(datetime.timezone.utc)
    driver.suspend_reason = reason
    driver.is_online = False
    db.commit()
    db.refresh(driver)
    return _driver_to_response(driver, db)


@router.post("/drivers/{driver_id}/location", response_model=DriverResponse)
def update_driver_location(
    driver_id: UUID,
    data: DriverLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.current_latitude = data.latitude
    driver.current_longitude = data.longitude
    driver.last_location_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(driver)
    return _driver_to_response(driver, db)


# =========================================================
# VEHICLE ENDPOINTS
# =========================================================

@router.get("/vehicles", response_model=VehicleListResponse)
def list_vehicles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Vehicle)
    if is_active is not None:
        q = q.filter(Vehicle.is_active == is_active)
    if search:
        q = q.filter(
            or_(
                Vehicle.plate_number.ilike(f"%{search}%"),
                Vehicle.brand.ilike(f"%{search}%"),
                Vehicle.model.ilike(f"%{search}%"),
            )
        )
    total = q.count()
    vehicles = q.order_by(Vehicle.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return VehicleListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[_vehicle_to_response(v) for v in vehicles],
    )


@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")
    return _vehicle_to_response(vehicle)


@router.post("/vehicles", response_model=VehicleResponse, status_code=201)
def create_vehicle(
    data: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_vehicle_manage)),
):
    existing = db.query(Vehicle).filter(Vehicle.plate_number.ilike(data.plate_number)).first()
    if existing:
        raise HTTPException(409, "Vehicle with this plate number already exists")
    vehicle = Vehicle(
        plate_number=data.plate_number,
        vehicle_type=data.vehicle_type,
        brand=data.brand,
        model=data.model,
        year=data.year,
        color=data.color,
        capacity_kg=data.capacity_kg,
        volume_m3=data.volume_m3,
        license_expiry=data.license_expiry,
        insurance_expiry=data.insurance_expiry,
    )
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return _vehicle_to_response(vehicle)


@router.put("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_vehicle_manage)),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vehicle, field, value)
    db.commit()
    db.refresh(vehicle)
    return _vehicle_to_response(vehicle)


@router.delete("/vehicles/{vehicle_id}", status_code=204)
def deactivate_vehicle(
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_vehicle_manage)),
):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(404, "Vehicle not found")
    vehicle.is_active = False
    db.commit()


# =========================================================
# DELIVERY TRIP ENDPOINTS
# =========================================================

@router.get("/trips", response_model=DeliveryTripListResponse)
def list_delivery_trips(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: DeliveryTripStatus | None = Query(None, alias="status"),
    driver_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(DeliveryTrip)
    if status_filter:
        q = q.filter(DeliveryTrip.status == status_filter)
    if driver_id:
        q = q.filter(DeliveryTrip.driver_id == driver_id)
    total = q.count()
    trips = q.order_by(DeliveryTrip.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return DeliveryTripListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[_trip_to_response(t, db) for t in trips],
    )


@router.get("/trips/{trip_id}", response_model=DeliveryTripResponse)
def get_delivery_trip(
    trip_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Delivery trip not found")
    return _trip_to_response(trip, db)


@router.post("/trips/shipment/{shipment_id}/assign", response_model=DeliveryTripResponse)
def assign_driver_to_shipment(
    shipment_id: UUID,
    data: AssignDriverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_trip_assign)),
):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(404, "Shipment not found")
    driver = db.query(Driver).filter(Driver.id == data.driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    if driver.status == DriverStatus.suspended:
        raise HTTPException(400, "Driver is suspended")
    if driver.verification_status != DriverVerificationStatus.verified:
        raise HTTPException(400, "Driver is not verified")

    # Check KYC if exists
    if driver.kyc and not driver.kyc.is_verified:
        raise HTTPException(400, "Driver KYC is not verified")

    vehicle = None
    if data.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).first()
        if not vehicle:
            raise HTTPException(404, "Vehicle not found")
    elif driver.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == driver.vehicle_id).first()

    seller_order = db.query(SellerOrder).filter(
        SellerOrder.order_id == shipment.order_id,
        SellerOrder.seller_id == shipment.seller_id,
    ).first()
    if not seller_order:
        raise HTTPException(404, "Seller order not found for this shipment")

    order = db.query(Order).filter(Order.id == shipment.order_id).first()

    # Check if trip already exists
    existing = db.query(DeliveryTrip).filter(DeliveryTrip.shipment_id == shipment_id).first()
    if existing:
        existing.driver_id = driver.id
        existing.vehicle_id = vehicle.id if vehicle else None
        existing.status = DeliveryTripStatus.assigned
        db.commit()
        db.refresh(existing)
        trip = existing
    else:
        trip = DeliveryTrip(
            ref_code=_generate_ref_code(),
            shipment_id=shipment.id,
            seller_order_id=seller_order.id,
            driver_id=driver.id,
            vehicle_id=vehicle.id if vehicle else None,
            status=DeliveryTripStatus.assigned,
            delivery_address=f"{order.shipping_address.street}, {order.shipping_address.ward}, {order.shipping_address.district}" if order and order.shipping_address else None,
            otp=secrets.token_hex(3)[:6],
        )
        db.add(trip)
        db.flush()
        db.add(DeliveryTripEvent(
            trip_id=trip.id,
            status=DeliveryTripStatus.assigned,
            notes=f"Driver {driver.id} assigned to shipment {shipment.id}",
        ))

        # Create trip coordinate record with pickup/destination data
        seller = db.query(Seller).filter(Seller.id == seller_order.seller_id).first()
        pickup_addr = None
        if seller:
            pickup_addr = db.query(Address).filter(
                Address.user_id == seller.user_id,
                Address.is_default.is_(True),
            ).first()
            if not pickup_addr:
                pickup_addr = db.query(Address).filter(
                    Address.user_id == seller.user_id,
                ).first()

        dest_addr = order.shipping_address if order else None
        coord = DeliveryTripCoordinate(
            trip_id=trip.id,
            pickup_address=f"{pickup_addr.street}, {pickup_addr.ward}, {pickup_addr.district}" if pickup_addr else None,
            pickup_latitude=float(pickup_addr.latitude) if pickup_addr and pickup_addr.latitude else None,
            pickup_longitude=float(pickup_addr.longitude) if pickup_addr and pickup_addr.longitude else None,
            destination_address=trip.delivery_address,
            destination_latitude=float(dest_addr.latitude) if dest_addr and dest_addr.latitude else None,
            destination_longitude=float(dest_addr.longitude) if dest_addr and dest_addr.longitude else None,
        )
        db.add(coord)

        # Calculate and create trip fee record
        veh_type = vehicle.vehicle_type if vehicle else VehicleType.motorcycle
        try:
            fare_req = FareCalculationRequest(
                pickup_latitude=coord.pickup_latitude or -6.8234,
                pickup_longitude=coord.pickup_longitude or 39.2695,
                destination_latitude=coord.destination_latitude or -6.8123,
                destination_longitude=coord.destination_longitude or 39.2891,
                vehicle_type=veh_type,
            )
            fare_result = calculate_fare(db, fare_req)
            trip_fee = DeliveryTripFee(
                trip_id=trip.id,
                base_fare=fare_result.base_fare,
                distance_fare=fare_result.distance_fare,
                surge_fee=fare_result.surge_fee,
                vat_tax=fare_result.vat_tax,
                total_fare=fare_result.total_fare,
                currency=fare_result.currency,
            )
            db.add(trip_fee)
            # Update trip's estimated distance and delivery fee
            trip.estimated_distance_km = fare_result.distance_km
            trip.delivery_fee = fare_result.total_fare
        except Exception:
            pass

        db.commit()
        db.refresh(trip)

    # Update driver status
    driver.status = DriverStatus.on_delivery
    driver.is_online = True
    db.commit()

    # Notify customer about driver assignment
    try:
        order = db.query(Order).filter(Order.id == shipment.order_id).first()
        if order and order.user_id:
            notification_service.notify(
                db=db, user_id=order.user_id, event=NotificationEvent.driver_assigned,
                title="Driver Assigned",
                message=f"A driver has been assigned to your order {order.order_number}. The driver will pick up your package soon.",
                data={"order_number": order.order_number, "trip_ref": trip.ref_code},
                action_url=f"/orders/{order.id}",
                channels=[NotificationChannel.in_app, NotificationChannel.sms],
                commit=False, dispatch=True,
            )
            db.commit()
    except Exception:
        pass

    return _trip_to_response(trip, db)


@router.put("/trips/{trip_id}/status", response_model=DeliveryTripResponse)
def update_trip_status(
    trip_id: UUID,
    data: UpdateTripStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Delivery trip not found")

    old_status = trip.status
    trip.status = data.status

    if data.status == DeliveryTripStatus.picked_up:
        trip.pickup_at = datetime.datetime.now(datetime.timezone.utc)
    elif data.status == DeliveryTripStatus.delivered:
        trip.delivered_at = datetime.datetime.now(datetime.timezone.utc)
        # Update shipment status
        shipment = db.query(Shipment).filter(Shipment.id == trip.shipment_id).first()
        if shipment:
            shipment.status = ShipmentStatus.delivered
        # Update driver stats
        if trip.driver_id:
            driver = db.query(Driver).filter(Driver.id == trip.driver_id).first()
            if driver:
                driver.total_deliveries += 1
                driver.status = DriverStatus.online
    elif data.status == DeliveryTripStatus.failed:
        trip.failed_at = datetime.datetime.now(datetime.timezone.utc)
        trip.failure_reason = data.notes
        if trip.driver_id:
            driver = db.query(Driver).filter(Driver.id == trip.driver_id).first()
            if driver:
                driver.status = DriverStatus.online
    elif data.status == DeliveryTripStatus.cancelled:
        if trip.driver_id:
            driver = db.query(Driver).filter(Driver.id == trip.driver_id).first()
            if driver:
                driver.status = DriverStatus.online

    # Add event
    db.add(DeliveryTripEvent(
        trip_id=trip.id,
        status=data.status,
        latitude=data.latitude,
        longitude=data.longitude,
        notes=data.notes,
        created_by_id=current_user.id,
    ))

    db.commit()
    db.refresh(trip)

    # Send notifications based on trip status
    try:
        shipment = db.query(Shipment).filter(Shipment.id == trip.shipment_id).first()
        order = db.query(Order).filter(Order.id == shipment.order_id).first() if shipment else None
        if order and order.user_id:
            notif_map = {
                DeliveryTripStatus.out_for_delivery: (NotificationEvent.out_for_delivery, "Out for Delivery", f"Your order {order.order_number} is out for delivery and will arrive soon. OTP: {trip.otp}"),
                DeliveryTripStatus.delivered: (NotificationEvent.order_delivered, "Order Delivered", f"Your order {order.order_number} has been delivered successfully. Thank you for shopping with Xerin!"),
                DeliveryTripStatus.failed: (NotificationEvent.delivery_failed, "Delivery Failed", f"Delivery for your order {order.order_number} could not be completed. Reason: {data.notes or 'N/A'}"),
            }
            if data.status in notif_map:
                ev, title, msg = notif_map[data.status]
                notification_service.notify(
                    db=db, user_id=order.user_id, event=ev, title=title, message=msg,
                    data={"order_number": order.order_number, "trip_ref": trip.ref_code, "otp": trip.otp or ""},
                    action_url=f"/orders/{order.id}",
                    channels=[NotificationChannel.in_app, NotificationChannel.sms, NotificationChannel.email],
                    commit=False, dispatch=True,
                )
                db.commit()
            # Admin alert on delivery failure
            if data.status == DeliveryTripStatus.failed:
                notification_service.notify_admins(
                    db=db, event=NotificationEvent.admin_delivery_alert,
                    title="Delivery Failed",
                    message=f"Delivery for order {order.order_number} failed. Trip: {trip.ref_code}. Reason: {data.notes or 'N/A'}",
                    data={"order_number": order.order_number, "trip_ref": trip.ref_code},
                    channels=[NotificationChannel.in_app, NotificationChannel.email],
                )
    except Exception:
        pass

    return _trip_to_response(trip, db)


@router.get("/trips/driver/{driver_id}", response_model=DeliveryTripListResponse)
def list_driver_trips(
    driver_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: DeliveryTripStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(DeliveryTrip).filter(DeliveryTrip.driver_id == driver_id)
    if status_filter:
        q = q.filter(DeliveryTrip.status == status_filter)
    total = q.count()
    trips = q.order_by(DeliveryTrip.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return DeliveryTripListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[_trip_to_response(t, db) for t in trips],
    )


# =========================================================
# SELLER STOCK TRANSFER ENDPOINTS
# =========================================================

@router.get("/stock-transfers", response_model=StockTransferListResponse)
def list_stock_transfers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: StockTransferStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SellerStockTransfer)
    # Sellers see only their own transfers; admins see all
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if seller:
        q = q.filter(SellerStockTransfer.seller_id == seller.id)
    if status_filter:
        q = q.filter(SellerStockTransfer.status == status_filter)
    total = q.count()
    transfers = q.order_by(SellerStockTransfer.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return StockTransferListResponse(
        total=total,
        page=page,
        page_size=page_size,
        results=[_transfer_to_response(t, db) for t in transfers],
    )


@router.get("/stock-transfers/{transfer_id}", response_model=StockTransferResponse)
def get_stock_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transfer = db.query(SellerStockTransfer).filter(SellerStockTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(404, "Stock transfer not found")
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if seller and transfer.seller_id != seller.id:
        raise HTTPException(403, "You can only view your own stock transfers")
    return _transfer_to_response(transfer, db)


@router.post("/stock-transfers", response_model=StockTransferResponse, status_code=201)
def create_stock_transfer(
    data: StockTransferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = _get_seller_from_user(db, current_user)
    warehouse = db.query(Warehouse).filter(Warehouse.id == data.warehouse_id).first()
    if not warehouse:
        raise HTTPException(404, "Warehouse not found")

    transfer = SellerStockTransfer(
        reference=_generate_transfer_ref(),
        seller_id=seller.id,
        warehouse_id=data.warehouse_id,
        status=StockTransferStatus.requested,
        origin_address=data.origin_address,
        expected_arrival_at=data.expected_arrival_at,
        transport_cost=data.transport_cost,
        notes=data.notes,
    )
    db.add(transfer)
    db.flush()

    for item in data.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(404, f"Product {item.product_id} not found")
        if product.seller_id != seller.id:
            raise HTTPException(403, f"You can only transfer your own products")
        db.add(SellerStockTransferItem(
            transfer_id=transfer.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            expected_quantity=item.expected_quantity,
        ))

    db.commit()
    db.refresh(transfer)
    return _transfer_to_response(transfer, db)


@router.put("/stock-transfers/{transfer_id}/status", response_model=StockTransferResponse)
def update_stock_transfer_status(
    transfer_id: UUID,
    data: StockTransferStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.stock_transfer_manage)),
):
    transfer = db.query(SellerStockTransfer).filter(SellerStockTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(404, "Stock transfer not found")

    transfer.status = data.status
    if data.status == StockTransferStatus.approved:
        pass
    elif data.status == StockTransferStatus.in_transit:
        transfer.dispatched_at = datetime.datetime.now(datetime.timezone.utc)
    elif data.status == StockTransferStatus.received:
        transfer.received_at = datetime.datetime.now(datetime.timezone.utc)
    elif data.status == StockTransferStatus.rejected:
        transfer.rejection_reason = data.rejection_reason
    if data.notes:
        transfer.notes = data.notes

    db.commit()
    db.refresh(transfer)

    # Notify seller about transfer status change
    try:
        seller = db.query(Seller).filter(Seller.id == transfer.seller_id).first()
        if seller and seller.user_id:
            notif_map = {
                StockTransferStatus.approved: (NotificationEvent.stock_transfer_approved, "Transfer Approved", f"Your stock transfer {transfer.reference} has been approved and is being processed."),
                StockTransferStatus.in_transit: (NotificationEvent.stock_transfer_approved, "Transfer In Transit", f"Your stock transfer {transfer.reference} has been dispatched to the warehouse."),
                StockTransferStatus.received: (NotificationEvent.stock_transfer_received, "Transfer Received", f"Your stock transfer {transfer.reference} has been received at the warehouse."),
                StockTransferStatus.rejected: (NotificationEvent.stock_transfer_rejected, "Transfer Rejected", f"Your stock transfer {transfer.reference} has been rejected. Reason: {data.rejection_reason or 'N/A'}"),
            }
            if data.status in notif_map:
                ev, title, msg = notif_map[data.status]
                notification_service.notify(
                    db=db, user_id=seller.user_id, event=ev, title=title, message=msg,
                    data={"reference": transfer.reference, "status": data.status.value},
                    channels=[NotificationChannel.in_app, NotificationChannel.sms, NotificationChannel.email],
                    commit=False, dispatch=True,
                )
                db.commit()
    except Exception:
        pass

    return _transfer_to_response(transfer, db)


@router.post("/stock-transfers/{transfer_id}/receive", response_model=StockTransferResponse)
def receive_stock_transfer(
    transfer_id: UUID,
    data: ReceiveStockTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.stock_transfer_manage)),
):
    transfer = db.query(SellerStockTransfer).filter(SellerStockTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(404, "Stock transfer not found")
    if transfer.status not in (StockTransferStatus.in_transit, StockTransferStatus.approved):
        raise HTTPException(400, f"Cannot receive transfer in {transfer.status} status")

    for recv_item in data.items:
        item = db.query(SellerStockTransferItem).filter(
            SellerStockTransferItem.id == recv_item.item_id,
            SellerStockTransferItem.transfer_id == transfer_id,
        ).first()
        if not item:
            raise HTTPException(404, f"Transfer item {recv_item.item_id} not found")
        if recv_item.received_quantity > item.expected_quantity:
            raise HTTPException(400, f"Received quantity exceeds expected for item {item.id}")
        item.received_quantity = recv_item.received_quantity

        # Add to warehouse inventory
        if recv_item.received_quantity > 0:
            inv = db.query(WarehouseInventory).filter(
                WarehouseInventory.warehouse_id == transfer.warehouse_id,
                WarehouseInventory.product_id == item.product_id,
                WarehouseInventory.variant_id == item.variant_id,
                WarehouseInventory.seller_id == transfer.seller_id,
            ).first()
            if inv:
                inv.quantity += recv_item.received_quantity
                inv.available_quantity += recv_item.received_quantity
            else:
                db.add(WarehouseInventory(
                    warehouse_id=transfer.warehouse_id,
                    product_id=item.product_id,
                    variant_id=item.variant_id,
                    seller_id=transfer.seller_id,
                    quantity=recv_item.received_quantity,
                    available_quantity=recv_item.received_quantity,
                ))

    transfer.status = StockTransferStatus.received
    transfer.received_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(transfer)
    return _transfer_to_response(transfer, db)


# =========================================================
# LOGISTICS DASHBOARD
# =========================================================

@router.get("/dashboard")
def logistics_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_read)),
):
    total_drivers = db.query(Driver).count()
    online_drivers = db.query(Driver).filter(Driver.is_online.is_(True)).count()
    on_delivery = db.query(Driver).filter(Driver.status == DriverStatus.on_delivery).count()
    pending_verification = db.query(Driver).filter(Driver.verification_status == DriverVerificationStatus.pending).count()
    total_vehicles = db.query(Vehicle).count()
    active_vehicles = db.query(Vehicle).filter(Vehicle.is_active.is_(True)).count()

    trip_counts = {}
    for ts in DeliveryTripStatus:
        trip_counts[ts.value] = db.query(DeliveryTrip).filter(DeliveryTrip.status == ts).count()

    transfer_counts = {}
    for ss in StockTransferStatus:
        transfer_counts[ss.value] = db.query(SellerStockTransfer).filter(SellerStockTransfer.status == ss).count()

    return {
        "drivers": {
            "total": total_drivers,
            "online": online_drivers,
            "on_delivery": on_delivery,
            "pending_verification": pending_verification,
        },
        "vehicles": {
            "total": total_vehicles,
            "active": active_vehicles,
        },
        "trips": trip_counts,
        "stock_transfers": transfer_counts,
    }


# =========================================================
# TRIP COORDINATES & FEES
# =========================================================

@router.get("/trips/{trip_id}/coordinates")
def get_trip_coordinates(
    trip_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.logistics_read)),
):
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    if not trip.coordinate:
        raise HTTPException(404, "Coordinates not recorded for this trip")
    coord = trip.coordinate
    return {
        "id": str(coord.id),
        "trip_id": str(coord.trip_id),
        "pickup_latitude": coord.pickup_latitude,
        "pickup_longitude": coord.pickup_longitude,
        "pickup_address": coord.pickup_address,
        "destination_latitude": coord.destination_latitude,
        "destination_longitude": coord.destination_longitude,
        "destination_address": coord.destination_address,
        "intermediate_coordinates": coord.intermediate_coordinates,
        "intermediate_addresses": coord.intermediate_addresses,
        "driver_accept_latitude": coord.driver_accept_latitude,
        "driver_accept_longitude": coord.driver_accept_longitude,
        "start_latitude": coord.start_latitude,
        "start_longitude": coord.start_longitude,
        "drop_latitude": coord.drop_latitude,
        "drop_longitude": coord.drop_longitude,
        "is_reached_destination": coord.is_reached_destination,
        "created_at": coord.created_at.isoformat() if coord.created_at else None,
    }


@router.put("/trips/{trip_id}/coordinates")
def update_trip_coordinates(
    trip_id: UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_trip_assign)),
):
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    if not trip.coordinate:
        coord = DeliveryTripCoordinate(trip_id=trip_id)
        db.add(coord)
        db.flush()
    else:
        coord = trip.coordinate

    allowed_fields = [
        "pickup_latitude", "pickup_longitude", "pickup_address",
        "destination_latitude", "destination_longitude", "destination_address",
        "intermediate_coordinates", "intermediate_addresses",
        "driver_accept_latitude", "driver_accept_longitude",
        "start_latitude", "start_longitude",
        "drop_latitude", "drop_longitude",
        "is_reached_destination",
    ]
    for field in allowed_fields:
        if field in data:
            setattr(coord, field, data[field])
    db.commit()
    db.refresh(coord)
    return {"message": "Coordinates updated", "is_reached_destination": coord.is_reached_destination}


@router.get("/trips/{trip_id}/fee")
def get_trip_fee(
    trip_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.logistics_read)),
):
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    if not trip.fee:
        raise HTTPException(404, "Fee not recorded for this trip")
    fee = trip.fee
    return {
        "id": str(fee.id),
        "trip_id": str(fee.trip_id),
        "base_fare": str(fee.base_fare),
        "distance_fare": str(fee.distance_fare),
        "waiting_fee": str(fee.waiting_fee),
        "idle_fee": str(fee.idle_fee),
        "delay_fee": str(fee.delay_fee),
        "cancellation_fee": str(fee.cancellation_fee),
        "return_fee": str(fee.return_fee),
        "surge_fee": str(fee.surge_fee),
        "vat_tax": str(fee.vat_tax),
        "admin_commission": str(fee.admin_commission),
        "tips": str(fee.tips),
        "total_fare": str(fee.total_fare),
        "currency": fee.currency,
        "created_at": fee.created_at.isoformat() if fee.created_at else None,
    }


@router.put("/trips/{trip_id}/fee")
def update_trip_fee(
    trip_id: UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_manage)),
):
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    if not trip.fee:
        fee = DeliveryTripFee(trip_id=trip_id)
        db.add(fee)
        db.flush()
    else:
        fee = trip.fee

    allowed_fields = [
        "base_fare", "distance_fare", "waiting_fee", "idle_fee",
        "delay_fee", "cancellation_fee", "return_fee", "surge_fee",
        "vat_tax", "admin_commission", "tips", "total_fare", "currency",
    ]
    for field in allowed_fields:
        if field in data:
            setattr(fee, field, data[field])
    db.commit()
    db.refresh(fee)
    return {"message": "Fee updated", "total_fare": str(fee.total_fare)}


@router.post("/trips/{trip_id}/recalculate-fee")
def recalculate_trip_fee(
    trip_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.logistics_manage)),
):
    """Recalculate fee for a trip based on current zone/surge config."""
    trip = db.query(DeliveryTrip).filter(DeliveryTrip.id == trip_id).first()
    if not trip:
        raise HTTPException(404, "Trip not found")
    coord = trip.coordinate
    if not coord or not coord.pickup_latitude or not coord.destination_latitude:
        raise HTTPException(400, "Trip coordinates not available for fare calculation")

    vehicle = None
    if trip.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == trip.vehicle_id).first()

    veh_type = vehicle.vehicle_type if vehicle else VehicleType.motorcycle
    fare_req = FareCalculationRequest(
        pickup_latitude=coord.pickup_latitude,
        pickup_longitude=coord.pickup_longitude,
        destination_latitude=coord.destination_latitude,
        destination_longitude=coord.destination_longitude,
        vehicle_type=veh_type,
    )
    fare_result = calculate_fare(db, fare_req)

    if not trip.fee:
        fee = DeliveryTripFee(trip_id=trip_id)
        db.add(fee)
    else:
        fee = trip.fee

    fee.base_fare = fare_result.base_fare
    fee.distance_fare = fare_result.distance_fare
    fee.surge_fee = fare_result.surge_fee
    fee.vat_tax = fare_result.vat_tax
    fee.total_fare = fare_result.total_fare
    fee.currency = fare_result.currency

    trip.estimated_distance_km = fare_result.distance_km
    trip.delivery_fee = fare_result.total_fare

    db.commit()
    db.refresh(fee)
    return {
        "message": "Fee recalculated",
        "total_fare": str(fee.total_fare),
        "distance_km": str(fare_result.distance_km),
        "zone_name": fare_result.zone_name,
    }
