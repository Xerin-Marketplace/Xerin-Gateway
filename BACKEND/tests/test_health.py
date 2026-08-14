def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert "Xerin Marketplace API" in body["message"]
    assert body["environment"] == "testing"


def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
