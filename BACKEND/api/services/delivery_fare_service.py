from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.enums import FareType, SurgePricingType, SurgeScheduleType, VehicleType
from api.models import DeliveryFare, DeliveryZone, SurgePricing
from api.schemas import FareCalculationRequest, FareCalculationResponse


def _round2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> Decimal:
    """Calculate distance between two coordinates in km using haversine formula."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _round2(Decimal(str(R * c)))


def _find_zone_for_coordinates(db: Session, lat: float, lon: float) -> DeliveryZone | None:
    """Find the delivery zone that contains the given coordinates."""
    zones = db.query(DeliveryZone).filter(DeliveryZone.is_active.is_(True)).all()
    for zone in zones:
        if zone.center_latitude and zone.center_longitude and zone.radius_km:
            dist = float(haversine_distance(lat, lon, zone.center_latitude, zone.center_longitude))
            if dist <= float(zone.radius_km):
                return zone
        if zone.boundaries:
            bounds = zone.boundaries
            if "polygon" in bounds:
                if _point_in_polygon(lat, lon, bounds["polygon"]):
                    return zone
            elif "min_lat" in bounds and "max_lat" in bounds:
                if bounds["min_lat"] <= lat <= bounds["max_lat"] and bounds["min_lon"] <= lon <= bounds["max_lon"]:
                    return zone
    return None


def _point_in_polygon(lat: float, lon: float, polygon: list) -> bool:
    """Ray casting algorithm to check if point is inside polygon."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]
        yj, xj = polygon[j][0], polygon[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _get_applicable_fare(
    db: Session, zone_id, vehicle_type: VehicleType | None, fare_type: FareType = FareType.delivery
) -> DeliveryFare | None:
    """Get the applicable fare for a zone and vehicle type."""
    q = db.query(DeliveryFare).filter(
        DeliveryFare.zone_id == zone_id,
        DeliveryFare.fare_type == fare_type,
        DeliveryFare.is_active.is_(True),
    )
    if vehicle_type:
        fare = q.filter(DeliveryFare.vehicle_type == vehicle_type).first()
        if fare:
            return fare
    # Fall back to generic fare (no vehicle type specified)
    return q.filter(DeliveryFare.vehicle_type.is_(None)).first()


def _get_active_surge(
    db: Session, zone_id, vehicle_type: VehicleType | None
) -> SurgePricing | None:
    """Get active surge pricing applicable to the zone and vehicle type."""
    now = datetime.now(timezone.utc)
    current_day = now.weekday()  # 0=Monday, 6=Sunday
    current_time = now.time()

    surges = db.query(SurgePricing).filter(
        SurgePricing.is_active.is_(True),
        (SurgePricing.zone_id == zone_id) | (SurgePricing.zone_id.is_(None)),
    ).all()

    for surge in surges:
        # Check schedule
        if surge.schedule_type == SurgeScheduleType.time_based:
            if surge.start_time and surge.end_time:
                if not (surge.start_time <= current_time <= surge.end_time):
                    continue
            if surge.days_of_week and current_day not in surge.days_of_week:
                continue

        # Check vehicle type applicability
        if surge.surge_type == SurgePricingType.specific_category:
            if surge.vehicle_type and vehicle_type and surge.vehicle_type != vehicle_type:
                continue

        return surge

    return None


def calculate_fare(db: Session, request: FareCalculationRequest) -> FareCalculationResponse:
    """Calculate delivery fare based on distance, zone, surge pricing, and additional fees."""
    # Calculate distance
    distance_km = haversine_distance(
        request.pickup_latitude, request.pickup_longitude,
        request.destination_latitude, request.destination_longitude,
    )

    # Find zone
    zone = None
    if request.zone_id:
        zone = db.query(DeliveryZone).filter(DeliveryZone.id == request.zone_id).first()
    if not zone:
        zone = _find_zone_for_coordinates(db, request.pickup_latitude, request.pickup_longitude)

    # Get fare config
    fare = None
    if zone:
        fare = _get_applicable_fare(db, zone.id, request.vehicle_type)
    if not fare:
        # Use system defaults if no zone-specific fare
        base_fare = Decimal("2000")
        per_km = Decimal("500")
        waiting_per_min = Decimal("50")
        idle_per_min = Decimal("30")
        delay_per_min = Decimal("100")
        cancel_pct = Decimal("10")
        min_cancel = Decimal("500")
        min_fare = Decimal("2000")
        max_fare = None
    else:
        base_fare = fare.base_fare
        per_km = fare.per_km_fare
        waiting_per_min = fare.waiting_fee_per_min
        idle_per_min = fare.idle_fee_per_min
        delay_per_min = fare.trip_delay_fee_per_min
        cancel_pct = fare.cancellation_fee_percent
        min_cancel = fare.min_cancellation_fee
        min_fare = fare.min_fare
        max_fare = fare.max_fare

    # Calculate components
    distance_fare = _round2(distance_km * per_km)
    waiting_fee = _round2(Decimal(str(request.waiting_minutes)) * waiting_per_min)
    idle_fee = _round2(Decimal(str(request.idle_minutes)) * idle_per_min)
    delay_fee = _round2(Decimal(str(request.delay_minutes)) * delay_per_min)

    # Cancellation fee
    cancellation_fee = Decimal("0")
    if request.is_cancelled:
        subtotal_before = base_fare + distance_fare + waiting_fee + idle_fee + delay_fee
        cancellation_fee = _round2(subtotal_before * cancel_pct / Decimal("100"))
        if cancellation_fee < min_cancel:
            cancellation_fee = min_cancel

    # Surge pricing
    surge_percentage = Decimal("0")
    surge_fee = Decimal("0")
    surge = None
    if zone:
        surge = _get_active_surge(db, zone.id, request.vehicle_type)
    if surge:
        surge_percentage = surge.surge_percentage
        subtotal_before_surge = base_fare + distance_fare + waiting_fee + idle_fee + delay_fee
        surge_fee = _round2(subtotal_before_surge * surge_percentage / Decimal("100"))

    # Subtotal
    subtotal = base_fare + distance_fare + waiting_fee + idle_fee + delay_fee + surge_fee

    # VAT (18% Tanzania)
    vat_percent = Decimal("18")
    vat_tax = _round2(subtotal * vat_percent / Decimal("100"))

    # Coupon discount
    coupon_discount = request.coupon_discount or Decimal("0")

    # Total
    total_fare = subtotal + vat_tax - coupon_discount + cancellation_fee

    # Apply min/max fare constraints
    if total_fare < min_fare:
        total_fare = min_fare
    if max_fare and total_fare > max_fare:
        total_fare = max_fare

    total_fare = _round2(total_fare)

    return FareCalculationResponse(
        base_fare=_round2(base_fare),
        distance_km=distance_km,
        distance_fare=distance_fare,
        waiting_fee=waiting_fee,
        idle_fee=idle_fee,
        delay_fee=delay_fee,
        cancellation_fee=_round2(cancellation_fee),
        surge_percentage=surge_percentage,
        surge_fee=surge_fee,
        subtotal=_round2(subtotal),
        vat_tax=vat_tax,
        coupon_discount=_round2(coupon_discount),
        total_fare=total_fare,
        currency="TZS",
        zone_name=zone.name if zone else None,
    )
