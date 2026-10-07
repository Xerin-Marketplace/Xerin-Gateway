from api.enums import InventoryReservationStatus
from api.models import Inventory, InventoryReservation, Order
from api.services.inventory_reservations import commit_order_reservations, release_expired_reservations


def test_inventory_reservation_model_contract():
    assert InventoryReservation.__tablename__ == "inventory_reservations"
    assert hasattr(InventoryReservation, "expires_at")
    assert hasattr(InventoryReservation, "committed_at")
    assert hasattr(InventoryReservation, "released_at")


def test_reservation_status_contract():
    assert {x.value for x in InventoryReservationStatus} == {"active", "committed", "released", "expired", "cancelled"}


def test_order_and_inventory_relationships_exist():
    assert hasattr(Order, "inventory_reservations")
    assert hasattr(Inventory, "reservations")


def test_reservation_services_exist():
    assert callable(commit_order_reservations)
    assert callable(release_expired_reservations)
