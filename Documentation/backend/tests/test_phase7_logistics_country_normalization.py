from api.countries import canonical_country, country_key
from api.schemas import ShippingZoneCreate

def test_country_aliases_are_canonical():
    assert canonical_country("UAE") == "United Arab Emirates"
    assert canonical_country("UK") == "United Kingdom"
    assert canonical_country("USA") == "United States"
    assert canonical_country("TZ") == "Tanzania"

def test_shipping_zone_normalizes_country():
    zone = ShippingZoneCreate(
        name="UAE export",
        country="UAE",
        scope="international",
        covers_entire_country=True,
        supports_domestic_delivery=False,
        supports_cross_border_inbound=False,
        supports_cross_border_outbound=True,
    )
    assert zone.country == "United Arab Emirates"

def test_entire_country_still_requires_route_capability():
    try:
        ShippingZoneCreate(
            name="Invalid",
            country="Tanzania",
            scope="international",
            covers_entire_country=True,
            supports_domestic_delivery=False,
            supports_cross_border_inbound=False,
            supports_cross_border_outbound=False,
        )
    except Exception:
        return
    raise AssertionError("Expected route capability validation to fail")

def test_country_key_treats_aliases_as_same_country():
    assert country_key("UAE") == country_key("United Arab Emirates")
