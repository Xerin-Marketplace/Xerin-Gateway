from api.services.map_location_service import _address_fields, _component_map_legacy, _component_map_new

def test_task2_map_routes_exist(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/locations/map/config" in paths
    assert "/api/v1/locations/map/autocomplete" in paths
    assert "/api/v1/locations/map/places/{place_id}" in paths
    assert "/api/v1/locations/map/reverse-geocode" in paths

def test_new_google_address_components_are_normalized():
    components = [
        {"longText":"Tanzania","shortText":"TZ","types":["country"]},
        {"longText":"Dar es Salaam","shortText":"Dar es Salaam","types":["administrative_area_level_1"]},
        {"longText":"Kinondoni","shortText":"Kinondoni","types":["administrative_area_level_2"]},
        {"longText":"Mikocheni","shortText":"Mikocheni","types":["locality"]},
        {"longText":"Old Bagamoyo Road","shortText":"Old Bagamoyo Rd","types":["route"]},
    ]
    address = _address_fields(_component_map_new(components))
    assert address["country_code"] == "TZ"
    assert address["region"] == "Dar es Salaam"
    assert address["city"] == "Mikocheni"
    assert address["district"] == "Kinondoni"

def test_legacy_components_are_normalized():
    components = [
        {"long_name":"Tanzania","short_name":"TZ","types":["country"]},
        {"long_name":"Dar es Salaam","short_name":"DSM","types":["administrative_area_level_1"]},
        {"long_name":"Kinondoni","short_name":"Kinondoni","types":["administrative_area_level_2"]},
    ]
    address = _address_fields(_component_map_legacy(components))
    assert address["country_code"] == "TZ"
    assert address["region"] == "Dar es Salaam"
