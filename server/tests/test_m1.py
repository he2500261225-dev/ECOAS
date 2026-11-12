from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, username: str = "operator") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_health():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"


def test_login_rejects_wrong_password():
    with TestClient(app) as client:
        resp = client.post("/api/auth/login", json={"username": "operator", "password": "bad"})
        assert resp.status_code == 401


def test_dashboard_summary_requires_auth():
    with TestClient(app) as client:
        assert client.get("/api/dashboard/summary").status_code == 401


def test_dashboard_summary_shape():
    with TestClient(app) as client:
        token = _login(client)
        resp = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["kpis"]["product_total"] >= 5
        assert len(data["stores"]) >= 2
        assert len(data["trend"]) == 14
        assert any(item["stock"] <= item["threshold"] for item in data["stock_warnings"])


def test_products_list_has_lifecycle_stages():
    with TestClient(app) as client:
        token = _login(client)
        resp = client.get("/api/products", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        stages = {p["stage"] for p in resp.json()}
        assert "reviewed" in stages
        assert "draft" in stages


def test_manager_only_reset_is_guarded():
    with TestClient(app) as client:
        operator_token = _login(client, "operator")
        resp = client.post("/api/demo/reset", headers={"Authorization": f"Bearer {operator_token}"})
        assert resp.status_code == 403
