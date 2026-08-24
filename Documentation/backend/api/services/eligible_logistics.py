from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, selectinload

from api.enums import LogisticsCompanyStatus, LogisticsScope
from api.countries import country_key
from api.models import (
    Address,
    Cart,
    CartItem,
    LogisticsCompany,
    Product,
    ProductStatus,
    SellerPickupLocation,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)



class EligibleLogisticsError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        extra: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.extra = extra or {}


@dataclass(frozen=True)
class LocationFacts:
    country: str
    region: str
    city: str
    district: str | None = None
    ward: str | None = None
    postal_code: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None


def _norm(value: str | None) -> str:
    return (value or "").strip().casefold()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _scope_supports(scope, requested: str) -> bool:
    value = _enum_value(scope)
    if requested == "local":
        return value in {"local", "both"}
    return value in {"international", "both"}


def _zone_matches_location(zone: ShippingZone, location: LocationFacts) -> bool:
    if not zone.is_active:
        return False
    if country_key(zone.country) != country_key(location.country):
        return False
    if zone.covers_entire_country:
        return True

    region_rules = {_norm(item) for item in (zone.regions or []) if _norm(item)}
    city_rules = {_norm(item) for item in (zone.cities or []) if _norm(item)}
    district_rules = {_norm(item) for item in (zone.districts or []) if _norm(item)}
    ward_rules = {_norm(item) for item in (zone.wards or []) if _norm(item)}
    postal_rules = {_norm(item) for item in (zone.postal_codes or []) if _norm(item)}

    if region_rules and _norm(location.region) not in region_rules:
        return False
    if city_rules and _norm(location.city) not in city_rules:
        return False
    if district_rules and _norm(location.district) not in district_rules:
        return False
    if ward_rules and _norm(location.ward) not in ward_rules:
        return False
    if postal_rules and _norm(location.postal_code) not in postal_rules:
        return False
    if zone.coverage_geojson and not _geojson_contains_location(
        zone.coverage_geojson, location
    ):
        return False
    return True


def _point_in_ring(longitude: float, latitude: float, ring: list) -> bool:
    inside = False
    if len(ring) < 3:
        return False
    previous = ring[-1]
    for current in ring:
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            boundary_x = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < boundary_x:
                inside = not inside
        previous = current
    return inside


def _polygon_contains(longitude: float, latitude: float, polygon: list) -> bool:
    if not polygon or not _point_in_ring(longitude, latitude, polygon[0]):
        return False
    return not any(
        _point_in_ring(longitude, latitude, hole) for hole in polygon[1:]
    )


def _geojson_contains_location(geojson: dict, location: LocationFacts) -> bool:
    if location.latitude is None or location.longitude is None:
        return False
    longitude = float(location.longitude)
    latitude = float(location.latitude)
    geometry_type = geojson.get("type")
    coordinates = geojson.get("coordinates") or []
    if geometry_type == "Polygon":
        return _polygon_contains(longitude, latitude, coordinates)
    if geometry_type == "MultiPolygon":
        return any(
            _polygon_contains(longitude, latitude, polygon)
            for polygon in coordinates
        )
    return False


def _address_is_tanzania(address: Address) -> bool:
    return country_key(address.country) == "tanzania"


def _customer_address(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    delivery_mode: str,
) -> Address:
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == user_id)
        .first()
    )
    if address is None:
        raise EligibleLogisticsError(
            "Delivery address not found.",
            code="delivery_address_not_found",
            status_code=404,
        )

    if not address.delivery_ready:
        raise EligibleLogisticsError(
            "Confirm the exact delivery map pin and recipient details before selecting a logistics company.",
            code="delivery_address_not_ready",
            status_code=409,
            extra={"address_id": str(address.id)},
        )

    # Phase 3: eligibility is based on origin -> destination, not on whether
    # the destination happens to be Tanzania. `delivery_mode` remains in the
    # request for backwards compatibility with checkout/order schemas.
    return address


def _cart_seller_pickups(
    db: Session,
    *,
    user_id: UUID,
) -> list[dict]:
    """Resolve one shipping origin per store represented in the cart.

    Phase 3 makes Product.store_id the authoritative commercial origin.  Store
    coordinates/location are preferred because one seller may own stores in
    different countries.  A seller default pickup is retained only as a
    backwards-compatible fallback when the store itself has no usable GPS.
    """
    cart = (
        db.query(Cart)
        .options(
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .joinedload(Product.store),
            selectinload(Cart.items)
            .selectinload(CartItem.product)
            .joinedload(Product.seller),
        )
        .filter(Cart.user_id == user_id)
        .first()
    )
    if cart is None or not cart.items:
        raise EligibleLogisticsError("Cart is empty.", code="cart_empty", status_code=400)

    products = []
    for item in cart.items:
        product = item.product
        if product is None or not product.is_active or product.status != ProductStatus.approved:
            continue
        products.append(product)

    if not products:
        raise EligibleLogisticsError(
            "Cart does not contain any shippable products.",
            code="cart_has_no_shippable_products",
            status_code=409,
        )

    seller_ids = list({product.seller_id for product in products})
    default_pickups = (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id.in_(seller_ids),
            SellerPickupLocation.is_active.is_(True),
            SellerPickupLocation.is_default.is_(True),
        )
        .all()
    )
    pickup_by_seller = {row.seller_id: row for row in default_pickups}

    store_map: dict[UUID, object] = {}
    for product in products:
        if product.store is None:
            raise EligibleLogisticsError(
                "A cart product is not assigned to a store.",
                code="product_store_required",
                status_code=409,
                extra={"product_id": str(product.id)},
            )
        store_map[product.store_id] = product

    result = []
    for store_id, product in store_map.items():
        store = product.store
        fallback = pickup_by_seller.get(product.seller_id)

        country = (store.country or "").strip()
        region = (store.region or "").strip()
        city = (store.district or store.region or "").strip()
        district = (store.district or "").strip() or None
        ward = (store.ward or "").strip() or None
        latitude = store.latitude
        longitude = store.longitude
        source = "store"

        if not country or latitude is None or longitude is None:
            if fallback is None:
                raise EligibleLogisticsError(
                    "The product store needs a country and GPS coordinates before logistics can be calculated.",
                    code="store_shipping_origin_required",
                    status_code=409,
                    extra={"store_id": str(store.id), "store_name": store.store_name},
                )
            country = country or fallback.country
            region = region or fallback.region
            city = city or fallback.city
            district = district or fallback.district
            ward = ward or fallback.ward
            latitude = latitude if latitude is not None else fallback.latitude
            longitude = longitude if longitude is not None else fallback.longitude
            source = "store_with_seller_pickup_fallback"

        result.append({
            "seller_id": product.seller_id,
            "seller_name": product.seller.business_name,
            "store_id": store.id,
            "store_name": store.store_name,
            "origin_source": source,
            "pickup": fallback,
            "origin": LocationFacts(
                country=country,
                region=region,
                city=city,
                district=district,
                ward=ward,
                postal_code=getattr(fallback, "postal_code", None) if fallback else None,
                latitude=Decimal(str(latitude)),
                longitude=Decimal(str(longitude)),
            ),
        })

    return result


def _company_methods_with_rates(
    db: Session,
    *,
    delivery_mode: str,
    search: str | None,
    supports_cod: bool | None,
    supports_tracking: bool | None,
) -> list[LogisticsCompany]:
    query = (
        db.query(LogisticsCompany)
        .options(
            selectinload(LogisticsCompany.services)
            .selectinload(ShippingMethod.rates)
            .joinedload(ShippingRate.zone)
        )
        .filter(LogisticsCompany.status == LogisticsCompanyStatus.active)
    )

    # Phase 3 does not pre-filter by legacy local/international company scope.
    # Exact route capability is checked per origin/destination country zone.

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                LogisticsCompany.name.ilike(term),
                LogisticsCompany.code.ilike(term),
            )
        )

    if supports_cod is not None:
        query = query.filter(LogisticsCompany.supports_cod.is_(supports_cod))
    if supports_tracking is not None:
        query = query.filter(
            LogisticsCompany.supports_tracking.is_(supports_tracking)
        )

    return query.order_by(LogisticsCompany.name.asc()).all()


def _zone_supports_capability(zone: ShippingZone, capability: str) -> bool:
    return bool(getattr(zone, capability, False))


def _company_covers_location_capability(
    company: LogisticsCompany,
    location: LocationFacts,
    *,
    capability: str,
) -> bool:
    for method in company.services:
        if not method.is_active:
            continue
        for rate in method.rates:
            zone = rate.zone
            if not rate.is_active or zone is None:
                continue
            if zone.logistics_company_id not in (None, company.id):
                continue
            if not _zone_supports_capability(zone, capability):
                continue
            if _zone_matches_location(zone, location):
                return True
    return False


def _company_supports_route(
    company: LogisticsCompany,
    origin: LocationFacts,
    destination: LocationFacts,
) -> tuple[bool, str]:
    same_country = country_key(origin.country) == country_key(destination.country)

    if same_country:
        origin_ok = _company_covers_location_capability(
            company, origin, capability="supports_domestic_delivery"
        )
        destination_ok = _company_covers_location_capability(
            company, destination, capability="supports_domestic_delivery"
        )
        return origin_ok and destination_ok, "domestic"

    outbound_ok = _company_covers_location_capability(
        company, origin, capability="supports_cross_border_outbound"
    )
    inbound_ok = _company_covers_location_capability(
        company, destination, capability="supports_cross_border_inbound"
    )
    return outbound_ok and inbound_ok, "cross_border"


def _company_covers_location(
    company: LogisticsCompany,
    location: LocationFacts,
    *,
    delivery_mode: str | None = None,
) -> bool:
    for method in company.services:
        if not method.is_active:
            continue
        if delivery_mode is not None and not _scope_supports(
            method.scope, delivery_mode
        ):
            continue

        for rate in method.rates:
            if not rate.is_active or rate.zone is None:
                continue
            if rate.zone.logistics_company_id not in (None, company.id):
                continue
            if delivery_mode is not None and not _scope_supports(
                rate.zone.scope, delivery_mode
            ):
                continue
            if _zone_matches_location(rate.zone, location):
                return True

    return False


def _eligible_services_for_destination(
    company: LogisticsCompany,
    destination: LocationFacts,
    *,
    delivery_mode: str,
) -> list[dict]:
    results: dict[UUID, dict] = {}

    for method in company.services:
        if not method.is_active or not _scope_supports(method.scope, delivery_mode):
            continue

        has_matching_rate = any(
            rate.is_active
            and rate.zone is not None
            and rate.zone.logistics_company_id in (None, company.id)
            and _scope_supports(rate.zone.scope, delivery_mode)
            and _zone_matches_location(rate.zone, destination)
            for rate in method.rates
        )
        if not has_matching_rate:
            continue

        results[method.id] = {
            "method_id": method.id,
            "method_name": method.name,
            "service_code": method.service_code,
            "scope": method.scope,
            "min_delivery_days": method.min_delivery_days,
            "max_delivery_days": method.max_delivery_days,
            "supports_cod": bool(method.supports_cod and company.supports_cod),
            "supports_tracking": bool(
                method.supports_tracking and company.supports_tracking
            ),
        }

    return sorted(results.values(), key=lambda row: row["method_name"].casefold())


def find_eligible_logistics_companies(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    delivery_mode: str,
    page: int,
    page_size: int,
    search: str | None = None,
    supports_cod: bool | None = None,
    supports_tracking: bool | None = None,
) -> dict:
    """Return companies capable of every store-origin -> customer-destination leg."""
    address = _customer_address(
        db, user_id=user_id, address_id=address_id, delivery_mode=delivery_mode
    )
    origins = _cart_seller_pickups(db, user_id=user_id)
    destination = LocationFacts(
        country=address.country, region=address.region, city=address.city,
        district=address.district, ward=address.ward, postal_code=address.postal_code,
        latitude=address.latitude, longitude=address.longitude,
    )

    companies = _company_methods_with_rates(
        db, delivery_mode=delivery_mode, search=search,
        supports_cod=supports_cod, supports_tracking=supports_tracking,
    )

    eligible, excluded = [], []
    for company in companies:
        uncovered, route_types = [], []
        for row in origins:
            ok, route_type = _company_supports_route(company, row["origin"], destination)
            route_types.append(route_type)
            if not ok:
                uncovered.append(
                    f'{row["store_name"]} ({row["origin"].country}, {row["origin"].region}) → '
                    f'{destination.country}, {destination.region}'
                )

        if uncovered:
            excluded.append({
                "logistics_company_id": company.id, "name": company.name, "code": company.code,
                "reason_codes": ["origin_destination_route_not_supported"],
                "reasons": [
                    "The company does not have the required domestic or cross-border country capabilities for every store-to-customer route."
                ],
                "uncovered_sellers": uncovered,
            })
            continue

        # Services are presented from active methods that have at least one rate.
        services = []
        for method in company.services:
            if not method.is_active or not any(rate.is_active for rate in method.rates):
                continue
            services.append({
                "method_id": method.id, "method_name": method.name,
                "service_code": method.service_code, "scope": method.scope,
                "min_delivery_days": method.min_delivery_days,
                "max_delivery_days": method.max_delivery_days,
                "supports_cod": bool(method.supports_cod and company.supports_cod),
                "supports_tracking": bool(method.supports_tracking and company.supports_tracking),
            })
        if not services:
            continue

        eligible.append({
            "logistics_company_id": company.id, "name": company.name, "code": company.code,
            "scope": company.scope, "supports_cod": bool(company.supports_cod),
            "supports_tracking": bool(company.supports_tracking),
            "supports_webhooks": bool(company.supports_webhooks),
            "seller_count": len(origins), "covered_seller_count": len(origins),
            "route_types": sorted(set(route_types)),
            "services": sorted(services, key=lambda row: row["method_name"].casefold()),
        })

    total=len(eligible); total_pages=ceil(total/page_size) if total else 0
    page_rows=eligible[(page-1)*page_size:page*page_size]
    return {
        "address_id": address.id, "delivery_mode": delivery_mode,
        "destination_country": destination.country,
        "seller_count": len(origins), "total": total, "page": page,
        "page_size": page_size, "total_pages": total_pages,
        "sellers": [{
            "seller_id": row["seller_id"], "seller_name": row["seller_name"],
            "store_id": row["store_id"], "store_name": row["store_name"],
            "pickup_location_id": row["pickup"].id if row["pickup"] else row["store_id"],
            "pickup_label": row["pickup"].label if row["pickup"] else row["store_name"],
            "country": row["origin"].country, "region": row["origin"].region,
            "city": row["origin"].city, "latitude": row["origin"].latitude,
            "longitude": row["origin"].longitude,
        } for row in origins],
        "results": page_rows, "excluded_companies": excluded,
    }

