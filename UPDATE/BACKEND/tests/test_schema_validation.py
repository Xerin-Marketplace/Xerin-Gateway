from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from api.schemas import PaymentMethod
from api.schemas import (
    CouponCreate,
    PaymentInitiateRequest,
    ProductCreate,
    RegisterRequest,
    StoreOpeningHourCreate,
)


def test_registration_normalises_names_and_phone():
    value = RegisterRequest(
        first_name=" Adam ",
        last_name=" Test ",
        email="ADAM@example.com",
        phone="+255 700-000-001",
        password="StrongPassword123",
    )
    assert value.first_name == "Adam"
    assert value.last_name == "Test"
    assert value.phone == "+255700000001"


@pytest.mark.parametrize("password", ["weak", "alllowercase123", "ALLUPPERCASE123", "NoDigitsHere"])
def test_registration_rejects_weak_password(password):
    with pytest.raises(ValidationError):
        RegisterRequest(
            first_name="Adam",
            last_name="Test",
            email="adam@example.com",
            phone="+255700000001",
            password=password,
        )


def test_product_rejects_sale_price_above_price():
    with pytest.raises(ValidationError, match="Sale price cannot be greater than price"):
        ProductCreate(
            category_id=uuid4(),
            sku="SKU-001",
            name="Product",
            slug="product",
            price=Decimal("10000"),
            sale_price=Decimal("12000"),
            currency="TZS",
        )


def test_coupon_rejects_percentage_above_100():
    with pytest.raises(ValidationError, match="Percentage discount cannot exceed 100"):
        CouponCreate(
            code="SAVE",
            discount_type="percentage",
            discount_value=Decimal("101"),
        )


def test_coupon_rejects_invalid_date_range():
    start = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="valid_until must be later than valid_from"):
        CouponCreate(
            code="SAVE",
            discount_type="fixed_amount",
            discount_value=Decimal("500"),
            valid_from=start,
            valid_until=start - timedelta(minutes=1),
        )


def test_mobile_money_requires_provider_and_phone():
    with pytest.raises(ValidationError):
        PaymentInitiateRequest(order_id=uuid4(), method=PaymentMethod.mobile_money)


def test_opening_hours_reject_reverse_range():
    with pytest.raises(ValidationError):
        StoreOpeningHourCreate(
            day_of_week="monday",
            opening_time="17:00:00",
            closing_time="08:00:00",
            is_closed=False,
        )
