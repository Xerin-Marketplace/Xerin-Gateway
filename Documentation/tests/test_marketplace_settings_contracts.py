from decimal import Decimal
from types import SimpleNamespace

from api.enums import CommissionRuleType
from api.schemas import MarketplaceSettingsUpdate


def test_marketplace_settings_requires_complete_policy():
    data = MarketplaceSettingsUpdate(
        escrow_release_hours=48,
        dispute_period_hours=48,
        cod_allowed=True,
        international_delivery_allowed=False,
    )
    assert data.escrow_release_hours == 48
    assert data.cod_allowed is True


def test_marketplace_settings_hours_are_bounded():
    from pydantic import ValidationError
    try:
        MarketplaceSettingsUpdate(
            escrow_release_hours=0,
            dispute_period_hours=48,
            cod_allowed=False,
            international_delivery_allowed=False,
        )
    except ValidationError:
        return
    raise AssertionError("Expected invalid escrow release period to be rejected")

def test_commission_markup_example():
    base = Decimal("200.00")
    rate = Decimal("2")
    fee = (base * rate / Decimal("100")).quantize(Decimal("0.01"))
    assert fee == Decimal("4.00")
    assert base + fee == Decimal("204.00")
