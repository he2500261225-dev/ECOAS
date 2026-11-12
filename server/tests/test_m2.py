import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models import ReviewReport, SystemConfig


def _login(client: TestClient, username: str = "operator") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


def _create_product(client: TestClient, token: str, store_id: int) -> dict:
    resp = client.post(
        "/api/products",
        headers=_headers(token),
        json={
            "store_id": store_id,
            "name": _unique("M2 测试防晒衣"),
            "category": "防晒服饰",
            "description": "原纱型冰丝面料，UPF50+ 防晒，凉感透气。",
            "skus": [
                {
                    "spec_text": "颜色:雾霾蓝,尺码:M",
                    "price": 149,
                    "stock": 20,
                    "warn_threshold": 10,
                    "mappings": [
                        {
                            "platform": "taobao",
                            "platform_spec_name": "雾霾蓝/M",
                            "platform_price": 149,
                            "platform_sku_code": _unique("TM"),
                        }
                    ],
                },
                {
                    "spec_text": "颜色:月光白,尺码:L",
                    "price": 159,
                    "stock": 8,
                    "warn_threshold": 10,
                },
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_store_management_is_manager_only_and_masks_auth_ref():
    with TestClient(app) as client:
        operator = _login(client)
        resp = client.post(
            "/api/stores",
            headers=_headers(operator),
            json={"name": "越权店铺", "platform": "taobao"},
        )
        assert resp.status_code == 403

        manager = _login(client, "manager")
        created = client.post(
            "/api/stores",
            headers=_headers(manager),
            json={
                "name": _unique("测试店铺"),
                "platform": "douyin",
                "auth_status": "pending",
                "auth_ref": "oauth_plain_secret_1234",
            },
        )
        assert created.status_code == 201, created.text
        store = created.json()
        assert "****" in store["auth_ref"]
        assert "plain_secret" not in store["auth_ref"]

        updated = client.put(
            f"/api/stores/{store['id']}",
            headers=_headers(manager),
            json={"auth_status": "authorized"},
        )
        assert updated.status_code == 200
        assert updated.json()["auth_status"] == "authorized"

        operator_update = client.put(
            f"/api/stores/{store['id']}",
            headers=_headers(operator),
            json={"auth_status": "expired"},
        )
        assert operator_update.status_code == 403


def test_product_create_update_and_archive():
    with TestClient(app) as client:
        token = _login(client)
        stores = client.get("/api/stores", headers=_headers(token)).json()
        product = _create_product(client, token, stores[0]["id"])

        assert product["price_min"] == 149
        assert product["price_max"] == 159
        assert len(product["skus"]) == 2
        assert product["main_sku_id"] == product["skus"][0]["id"]
        assert product["skus"][0]["mappings"][0]["platform"] == "taobao"

        invalid = client.put(
            f"/api/products/{product['id']}",
            headers=_headers(token),
            json={"price_min": 200, "price_max": 100},
        )
        assert invalid.status_code == 400

        bad_main = client.put(
            f"/api/products/{product['id']}",
            headers=_headers(token),
            json={"main_sku_id": 999999},
        )
        assert bad_main.status_code == 400

        updated = client.put(
            f"/api/products/{product['id']}",
            headers=_headers(token),
            json={"name": _unique("改名后的商品"), "price_min": 139, "price_max": 169},
        )
        assert updated.status_code == 200
        assert updated.json()["price_min"] == 139

        archived = client.post(f"/api/products/{product['id']}/archive", headers=_headers(token))
        assert archived.status_code == 200
        assert archived.json()["archived"] is True

        listed = client.get("/api/products", headers=_headers(token)).json()
        assert all(item["id"] != product["id"] for item in listed)


def test_sku_stock_adjust_flows_and_mapping_crud():
    with TestClient(app) as client:
        token = _login(client)
        stores = client.get("/api/stores", headers=_headers(token)).json()
        product = _create_product(client, token, stores[0]["id"])
        sku = product["skus"][0]

        updated = client.put(
            f"/api/skus/{sku['id']}",
            headers=_headers(token),
            json={"price": 139, "warn_threshold": 15},
        )
        assert updated.status_code == 200
        assert updated.json()["price"] == 139
        assert updated.json()["warn_threshold"] == 15

        too_much = client.post(
            f"/api/skus/{sku['id']}/stock-adjust",
            headers=_headers(token),
            json={"change": -9999, "reason": "manual"},
        )
        assert too_much.status_code == 400

        adjusted = client.post(
            f"/api/skus/{sku['id']}/stock-adjust",
            headers=_headers(token),
            json={"change": 30, "reason": "restock"},
        )
        assert adjusted.status_code == 200, adjusted.text
        assert adjusted.json()["sku"]["stock"] == sku["stock"] + 30
        assert adjusted.json()["flow"]["stock_after"] == sku["stock"] + 30

        flows = client.get(f"/api/skus/{sku['id']}/stock-flows", headers=_headers(token)).json()
        assert flows and flows[0]["reason"] == "restock"

        mapping = client.post(
            f"/api/skus/{sku['id']}/mappings",
            headers=_headers(token),
            json={
                "platform": "douyin",
                "platform_spec_name": "雾霾蓝/M",
                "platform_price": 145,
                "platform_sku_code": _unique("DY"),
            },
        )
        assert mapping.status_code == 201, mapping.text
        mapping_id = mapping.json()["id"]

        duplicate = client.post(
            f"/api/skus/{sku['id']}/mappings",
            headers=_headers(token),
            json={
                "platform": "douyin",
                "platform_spec_name": "重复编码",
                "platform_sku_code": mapping.json()["platform_sku_code"],
            },
        )
        assert duplicate.status_code == 400

        changed = client.put(
            f"/api/mappings/{mapping_id}",
            headers=_headers(token),
            json={"platform_price": 148},
        )
        assert changed.status_code == 200
        assert changed.json()["platform_price"] == 148

        removed = client.delete(f"/api/mappings/{mapping_id}", headers=_headers(token))
        assert removed.status_code == 200

        new_sku = client.post(
            f"/api/products/{product['id']}/skus",
            headers=_headers(token),
            json={"spec_json": {"颜色": "黑色"}, "price": 149, "stock": 5, "warn_threshold": 3},
        )
        assert new_sku.status_code == 201
        deleted = client.delete(f"/api/skus/{new_sku.json()['id']}", headers=_headers(token))
        assert deleted.status_code == 200


def test_competitor_crud_and_mock_parse_draft():
    with TestClient(app) as client:
        token = _login(client)
        stores = client.get("/api/stores", headers=_headers(token)).json()
        product = _create_product(client, token, stores[0]["id"])

        created = client.post(
            f"/api/products/{product['id']}/competitors",
            headers=_headers(token),
            json={
                "platform": "taobao",
                "name": "蕉下 冰丝防晒衣",
                "price": 189,
                "params_json": {"UPF": "50+", "面料": "原纱型冰丝"},
                "sales_volume": 20000,
                "rating": 4.8,
            },
        )
        assert created.status_code == 201, created.text
        competitor = created.json()
        assert competitor["source"] == "manual"

        parsed = client.post(
            f"/api/products/{product['id']}/competitors/parse",
            headers=_headers(token),
            json={
                "text": (
                    "觅橘 轻户外防晒衣 | 抖音\n"
                    "价格：99 元，月销 8000，评分 4.6\n"
                    "UPF：40+，面料：涂层型，克重：110g\n"
                    "https://example.com/item/miju"
                )
            },
        )
        assert parsed.status_code == 200, parsed.text
        body = parsed.json()
        assert body["channel"] == "mock"
        assert body["drafts"]
        draft = body["drafts"][0]
        assert draft["source"] == "ai_parse"
        assert draft["parse_status"] == "draft"
        assert draft["platform"] == "douyin"
        assert draft["price"] == 99
        assert draft["sales_volume"] == 8000
        assert draft["params_json"]["UPF"] == "40+"

        saved = client.post(
            f"/api/products/{product['id']}/competitors",
            headers=_headers(token),
            json={**draft, "parse_status": "confirmed"},
        )
        assert saved.status_code == 201, saved.text
        assert saved.json()["parse_status"] == "confirmed"

        updated = client.put(
            f"/api/competitors/{competitor['id']}",
            headers=_headers(token),
            json={"price": 179},
        )
        assert updated.status_code == 200
        assert updated.json()["price"] == 179

        listed = client.get(
            f"/api/products/{product['id']}/competitors", headers=_headers(token)
        ).json()
        assert len(listed) == 2

        deleted = client.delete(
            f"/api/competitors/{competitor['id']}", headers=_headers(token)
        )
        assert deleted.status_code == 200


def test_diagnosis_versioning_editing_and_report_linkage():
    with TestClient(app) as client:
        token = _login(client)
        stores = client.get("/api/stores", headers=_headers(token)).json()
        product = _create_product(client, token, stores[0]["id"])

        first = client.post(
            f"/api/products/{product['id']}/diagnoses/generate",
            headers=_headers(token),
            json={},
        )
        assert first.status_code == 200, first.text
        v1 = first.json()
        assert v1["version"] == 1
        assert v1["status"] == "current"
        assert v1["channel"] == "mock"
        content = v1["content_json"]
        for key in (
            "audience",
            "price_analysis",
            "selling_points",
            "conversion_blockers",
            "optimization_directions",
        ):
            assert key in content
        assert len(content["selling_points"]) >= 3

        content["audience"]["persona"] = "人工修订后的目标客群描述"
        edited = client.put(
            f"/api/diagnoses/{v1['id']}",
            headers=_headers(token),
            json={"content_json": content},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["content_json"]["audience"]["persona"] == "人工修订后的目标客群描述"

        second = client.post(
            f"/api/products/{product['id']}/diagnoses/generate",
            headers=_headers(token),
            json={},
        )
        assert second.status_code == 200
        v2 = second.json()
        assert v2["version"] == 2
        assert v2["status"] == "current"

        versions = client.get(
            f"/api/products/{product['id']}/diagnoses", headers=_headers(token)
        ).json()
        assert [item["version"] for item in versions] == [2, 1]
        assert versions[1]["status"] == "history"
        assert versions[1]["content_json"]["audience"]["persona"] == "人工修订后的目标客群描述"

        history_edit = client.put(
            f"/api/diagnoses/{v1['id']}",
            headers=_headers(token),
            json={"content_json": content},
        )
        assert history_edit.status_code == 400

        invalid = client.put(
            f"/api/diagnoses/{v2['id']}",
            headers=_headers(token),
            json={"content_json": {"audience": "not-an-object"}},
        )
        assert invalid.status_code == 422

    # 复盘行动项 -> 下一轮诊断，版本自增且关联报告
    with TestClient(app) as client:
        token = _login(client)
        with SessionLocal() as db:
            report = db.scalar(select(ReviewReport).limit(1))
            assert report is not None
            report_id = report.id
            report_product_id = report.product_id
            expected_actions = report.structured_json.get("action_items") or []

        resp = client.post(
            f"/api/products/{report_product_id}/diagnoses/generate",
            headers=_headers(token),
            json={"source_report_id": report_id},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source_report_id"] == report_id
        assert data["version"] >= 2
        directions = data["content_json"]["optimization_directions"]
        assert any(action in directions for action in expected_actions)


def test_real_llm_failure_falls_back_and_never_leaks_key():
    with TestClient(app) as client:
        manager = _login(client, "manager")
        stores = client.get("/api/stores", headers=_headers(manager)).json()
        product = _create_product(client, manager, stores[0]["id"])

        secret = "sk-test-SECRET-123456"
        with SessionLocal() as db:
            row = db.scalar(select(SystemConfig).where(SystemConfig.key == "llm"))
            assert row is not None
            original = dict(row.value_json or {})
            row.value_json = {
                **original,
                "mode": "real",
                "provider": "anthropic",
                "base_url": "http://127.0.0.1:9",
                "api_key": secret,
                "model": "claude-test",
                "timeout_seconds": 2,
            }
            db.commit()

        try:
            resp = client.post(
                f"/api/products/{product['id']}/diagnoses/generate",
                headers=_headers(manager),
                json={},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["generate_channel"] == "mock_fallback"
            assert "fallback" in data["model"]
            assert data["content_json"]["audience"]["persona"]
            assert secret not in resp.text
        finally:
            with SessionLocal() as db:
                row = db.scalar(select(SystemConfig).where(SystemConfig.key == "llm"))
                assert row is not None
                row.value_json = original
                db.commit()
