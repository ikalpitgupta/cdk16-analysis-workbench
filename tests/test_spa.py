from fastapi.testclient import TestClient
from api.server import app

client = TestClient(app)

def test_spa_root():
    r = client.get("/")
    assert r.status_code == 200
    assert "<!doctype html>" in r.text.lower()
    assert "cdk16" in r.text.lower() or "workbench" in r.text.lower() or "viewport" in r.text.lower()

def test_spa_routes():
    for route in ["/variants", "/analysis", "/protein", "/structure", "/reports"]:
        r = client.get(route)
        assert r.status_code == 200
        assert "<!doctype html>" in r.text.lower()

def test_spa_api_404():
    r = client.get("/api/unknown_endpoint_404")
    assert r.status_code == 404
