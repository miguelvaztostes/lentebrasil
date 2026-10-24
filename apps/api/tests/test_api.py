from fastapi.testclient import TestClient

from lente_api.main import app


def test_health_contract() -> None:
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "lente-ribeirao-api",
        "version": "0.1.0",
    }
    assert response.headers["x-content-type-options"] == "nosniff"


def test_sector_routes_are_public_read_only_contracts() -> None:
    paths = TestClient(app).get("/api/openapi.json").json()["paths"]
    assert "/api/v1/sectors/economy" in paths
    assert "/api/v1/sectors/labor" in paths
    assert "/api/v1/sectors/infrastructure" in paths
    assert "/api/v1/sectors/overview" in paths
    assert set(paths["/api/v1/sectors/economy"]) == {"get"}
