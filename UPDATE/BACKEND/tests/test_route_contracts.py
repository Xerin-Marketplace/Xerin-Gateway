from collections import Counter

from api.main import api


def test_openapi_schema_builds():
    schema = api.openapi()
    assert schema["info"]["title"] == "Xerin Marketplace API"
    assert "/api/v1/auth/login" in schema["paths"]


def test_no_duplicate_method_path_pairs():
    pairs = []
    for route in api.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", None)
        for method in methods:
            if method not in {"HEAD", "OPTIONS"} and path:
                pairs.append((method, path))

    duplicates = [pair for pair, count in Counter(pairs).items() if count > 1]
    assert duplicates == [], f"Duplicate API routes found: {duplicates}"
