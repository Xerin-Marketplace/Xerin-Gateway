from pydantic import ValidationError
import pytest

from api.schemas import LogisticsCompanyOnboardCreate


def payload() -> dict:
    return {
        "company": {
            "name": "Fast Delivery Tanzania",
            "code": "fast-delivery-tz",
            "status": "pending",
            "scope": "local",
        },
        "administrator": {
            "first_name": "Asha",
            "last_name": "Juma",
            "email": "asha@example.com",
            "phone": "0712345678",
        },
    }


def test_onboarding_contract_accepts_pending_company():
    data = LogisticsCompanyOnboardCreate.model_validate(payload())
    assert data.company.status.value == "pending"
    assert data.administrator.email == "asha@example.com"


def test_onboarding_contract_rejects_active_company():
    data = payload()
    data["company"]["status"] = "active"
    with pytest.raises(ValidationError, match="must start as pending"):
        LogisticsCompanyOnboardCreate.model_validate(data)


def test_onboarding_contract_rejects_admin_supplied_password():
    data = payload()
    data["administrator"]["password"] = "AdminMustNotChooseThis123!"
    with pytest.raises(ValidationError):
        LogisticsCompanyOnboardCreate.model_validate(data)


def test_openapi_contains_atomic_logistics_onboarding(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    path = "/api/v1/logistics/companies/onboard"
    assert path in response.json()["paths"]
    assert "post" in response.json()["paths"][path]


def test_onboarding_requires_admin_authentication(client):
    response = client.post("/api/v1/logistics/companies/onboard", json=payload())
    assert response.status_code in {401, 403}
