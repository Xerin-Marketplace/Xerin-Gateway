from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from api.models import SellerOrder, SellerOrderPackage, SellerPickupLocation, Shipment


@dataclass
class ReadinessCheck:
    code: str
    label: str
    ready: bool
    blocking: bool = True
    detail: str | None = None


@dataclass
class FulfillmentReadiness:
    ready: bool
    checks: list[ReadinessCheck] = field(default_factory=list)
    pickup_location: SellerPickupLocation | None = None
    package: SellerOrderPackage | None = None
    shipment: Shipment | None = None

    @property
    def blockers(self) -> list[ReadinessCheck]:
        return [check for check in self.checks if check.blocking and not check.ready]

    @property
    def packages(self) -> list[SellerOrderPackage]:
        """Compatibility collection for readiness summaries.

        Phase 1 stores one package record per seller order. The response
        contract is already multi-package capable, so expose the current record
        as a collection without changing the persistence model.
        """
        return [self.package] if self.package is not None else []


def _positive(value) -> bool:
    if value is None:
        return False
    try:
        return Decimal(value) > 0
    except Exception:
        return False


def evaluate_seller_fulfillment_readiness(
    db: Session,
    *,
    seller_order: SellerOrder,
) -> FulfillmentReadiness:
    """Return a deterministic readiness assessment for READY_TO_SHIP.

    The policy intentionally validates only seller-side fulfillment facts in
    Phase 1. Customer destination GPS becomes mandatory in the customer phase.
    """
    pickup = (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id == seller_order.seller_id,
            SellerPickupLocation.is_active.is_(True),
            SellerPickupLocation.is_default.is_(True),
        )
        .first()
    )

    package = (
        db.query(SellerOrderPackage)
        .filter(SellerOrderPackage.seller_order_id == seller_order.id)
        .order_by(SellerOrderPackage.created_at.desc())
        .first()
    )

    shipment = (
        db.query(Shipment)
        .filter(
            Shipment.order_id == seller_order.order_id,
            Shipment.seller_id == seller_order.seller_id,
        )
        .first()
    )

    checks: list[ReadinessCheck] = []

    checks.append(
        ReadinessCheck(
            code="pickup_location",
            label="Active default pickup location",
            ready=pickup is not None,
            detail=(
                None
                if pickup is not None
                else "Configure an active default seller pickup location."
            ),
        )
    )

    checks.append(
        ReadinessCheck(
            code="pickup_gps",
            label="Pickup GPS coordinates",
            ready=bool(
                pickup is not None
                and pickup.latitude is not None
                and pickup.longitude is not None
            ),
            detail=(
                None
                if pickup is not None
                and pickup.latitude is not None
                and pickup.longitude is not None
                else "Pickup latitude and longitude are required."
            ),
        )
    )

    checks.append(
        ReadinessCheck(
            code="pickup_contact",
            label="Pickup contact",
            ready=bool(
                pickup is not None
                and (pickup.pickup_contact_name or "").strip()
                and (pickup.pickup_phone or "").strip()
            ),
            detail=(
                None
                if pickup is not None
                and (pickup.pickup_contact_name or "").strip()
                and (pickup.pickup_phone or "").strip()
                else "Pickup contact name and phone are required."
            ),
        )
    )

    checks.append(
        ReadinessCheck(
            code="package",
            label="Package prepared",
            ready=package is not None,
            detail=None if package is not None else "Prepare package details for this seller order.",
        )
    )

    checks.append(
        ReadinessCheck(
            code="package_confirmed",
            label="Package confirmed ready",
            ready=bool(package is not None and package.is_ready),
            detail=(
                None
                if package is not None and package.is_ready
                else "Confirm the package as ready before dispatch."
            ),
        )
    )

    checks.append(
        ReadinessCheck(
            code="package_weight",
            label="Package weight",
            ready=bool(package is not None and _positive(package.weight_kg)),
            detail=(
                None
                if package is not None and _positive(package.weight_kg)
                else "Package weight must be greater than zero."
            ),
        )
    )

    checks.append(
        ReadinessCheck(
            code="package_count",
            label="Package count",
            ready=bool(package is not None and (package.package_count or 0) > 0),
            detail=(
                None
                if package is not None and (package.package_count or 0) > 0
                else "Package count must be at least one."
            ),
        )
    )

    # Dimensions are useful for carrier integrations but are not a Phase 1
    # blocker because some product classes/carriers do not require them yet.
    dimensions_ready = bool(
        package is not None
        and _positive(package.length_cm)
        and _positive(package.width_cm)
        and _positive(package.height_cm)
    )
    checks.append(
        ReadinessCheck(
            code="package_dimensions",
            label="Package dimensions",
            ready=dimensions_ready,
            blocking=False,
            detail=(
                None
                if dimensions_ready
                else "Length, width and height are recommended for accurate logistics quoting."
            ),
        )
    )

    checks.append(
        ReadinessCheck(
            code="shipment",
            label="Seller shipment created",
            ready=shipment is not None,
            detail=None if shipment is not None else "Shipment has not been created for this seller order.",
        )
    )

    ready = all(check.ready for check in checks if check.blocking)
    return FulfillmentReadiness(
        ready=ready,
        checks=checks,
        pickup_location=pickup,
        package=package,
        shipment=shipment,
    )
