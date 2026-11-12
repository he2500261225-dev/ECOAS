import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import ASSET_DIR
from app.db import SessionLocal
from app.main import app
from app.models import SystemConfig
from app.seed import seed


def _login(client: TestClient, username: str = "operator") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _products(client: TestClient, token: str) -> list[dict]:
    resp = client.get("/api/products", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _find_product(client: TestClient, token: str, prefix: str) -> dict:
    product = next((item for item in _products(client, token) if item["name"].startswith(prefix)), None)
    assert product is not None, f"未找到服务商品：{prefix}"
    return product


def _snapshot_config(key: str) -> dict:
    with SessionLocal() as db:
        row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        assert row is not None
        return dict(row.value_json or {})


def _set_config(key: str, patch: dict) -> None:
    with SessionLocal() as db:
        row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        assert row is not None
        row.value_json = {**(row.value_json or {}), **patch}
        db.commit()


def _restore_config(key: str, value: dict) -> None:
    with SessionLocal() as db:
        row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
        assert row is not None
        row.value_json = value
        db.commit()


def _wait_task(client: TestClient, token: str, task_id: int, timeout: float = 10.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/api/tasks/{task_id}", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in {"succeeded", "failed", "timeout", "cancelled"}:
            return last
        time.sleep(0.05)
    raise AssertionError(f"任务未在 {timeout}s 内结束：{last}")


def _content_text(plan: dict) -> str:
    parts: list[str] = []
    for scheme in plan.get("image_schemes") or []:
        parts.extend(
            str(scheme.get(field) or "")
            for field in ("title", "layout", "copy", "main_selling_point", "visual_tip")
        )
    for script in plan.get("video_scripts") or []:
        parts.extend([str(script.get("title") or ""), str(script.get("hook_3s") or ""), str(script.get("closing_cta") or "")])
        for shot in script.get("shots") or []:
            parts.extend(
                str(shot.get(field) or "")
                for field in ("scene_desc", "voiceover", "cta_line")
            )
    return " ".join(parts)


def test_service_seed_is_incremental_idempotent_and_local():
    with TestClient(app) as client:
        token = _login(client)
        stores = client.get("/api/stores", headers=_headers(token)).json()
        local_stores = {item["name"] for item in stores if item["platform"] == "local"}
        assert {"净呼吸除甲醛", "洁净洗衣"} <= local_stores

        # 重复执行 seed 不应产生重复店铺 / 商品 / 诊断 / 创意方案
        with SessionLocal() as db:
            seed(db)
            seed(db)

        products = _products(client, token)
        air_items = [item for item in products if item["name"].startswith("净呼吸除甲醛")]
        laundry_items = [item for item in products if item["name"].startswith("洁净洗衣")]
        assert len(air_items) == 1
        assert len(laundry_items) == 1

        air, laundry = air_items[0], laundry_items[0]
        assert air["is_service"] is True
        assert laundry["is_service"] is True
        assert air["price_unit"] == "元/㎡"
        assert laundry["price_unit"] == "元/件起"
        assert air["stage"] == "diagnosed"
        assert laundry["stage"] == "creative_ready"

        air_detail = client.get(f"/api/products/{air['id']}", headers=_headers(token)).json()
        assert air_detail["is_service"] is True
        assert len(air_detail["skus"]) >= 3
        for sku in air_detail["skus"]:
            assert sku["stock"] == 9999
            assert sku["warn_threshold"] == 0
            assert sku["warning"] is False

        summary = client.get("/api/dashboard/summary", headers=_headers(token)).json()
        warning_product_ids = {item["product_id"] for item in summary["stock_warnings"]}
        assert air["id"] not in warning_product_ids
        assert laundry["id"] not in warning_product_ids

        # 本地生活平台出现在店铺列表中，服务商品计入商品/服务总数
        assert summary["kpis"]["product_total"] >= 7


def test_service_creative_meets_limits_and_uses_service_keywords():
    with TestClient(app) as client:
        token = _login(client)
        air = _find_product(client, token, "净呼吸除甲醛")
        laundry = _find_product(client, token, "洁净洗衣")

        generated = client.post(
            f"/api/products/{air['id']}/creative-plans/generate",
            headers=_headers(token),
            json={},
        )
        assert generated.status_code == 200, generated.text
        plan = generated.json()
        assert len(plan["image_schemes"]) >= 3
        assert len(plan["video_scripts"]) >= 3
        for script in plan["video_scripts"]:
            assert len(script["shots"]) >= 4
        air_text = _content_text(plan)
        for keyword in ("检测", "复检", "质保", "预约"):
            assert keyword in air_text, f"除甲醛获客方案缺少关键词：{keyword}"
        for forbidden in ("零甲醛", "100% 去除", "永久有效"):
            assert forbidden not in air_text

        laundry_plans = client.get(
            f"/api/products/{laundry['id']}/creative-plans", headers=_headers(token)
        ).json()
        assert laundry_plans, "洗衣店应预置创意方案"
        preloaded = laundry_plans[0]
        assert len(preloaded["image_schemes"]) >= 3
        assert len(preloaded["video_scripts"]) >= 3
        for script in preloaded["video_scripts"]:
            assert len(script["shots"]) >= 4
        laundry_text = _content_text(preloaded)
        for keyword in ("洗护", "取送", "上门"):
            assert keyword in laundry_text, f"洗衣店获客方案缺少关键词：{keyword}"
        for forbidden in ("100% 洗净", "绝对不伤衣"):
            assert forbidden not in laundry_text


def test_service_material_uses_service_template_and_tags():
    media = _snapshot_config("media")
    try:
        _set_config("media", {"delay_min": 0, "delay_max": 0, "fail_rate": 0.0})
        with TestClient(app) as client:
            token = _login(client)
            laundry = _find_product(client, token, "洁净洗衣")
            plans = client.get(
                f"/api/products/{laundry['id']}/creative-plans", headers=_headers(token)
            ).json()
            scheme = plans[0]["image_schemes"][0]
            task_resp = client.post(
                "/api/tasks",
                headers=_headers(token),
                json={"source_type": "image_scheme", "source_id": scheme["id"]},
            )
            assert task_resp.status_code == 201, task_resp.text
            task = _wait_task(client, token, task_resp.json()["id"])
            assert task["status"] == "succeeded", task
            assert task["result_asset_id"]

            assets = client.get(
                f"/api/products/{laundry['id']}/assets?type=image", headers=_headers(token)
            ).json()
            asset = next(item for item in assets if item["id"] == task["result_asset_id"])
            assert "获客素材" in asset["tags_json"]
            assert (ASSET_DIR / asset["filename"]).exists()
            content = (ASSET_DIR / asset["filename"]).read_text(encoding="utf-8")
            assert "获客素材" in content
            assert "模拟生成，仅供方案评审" in content
    finally:
        _restore_config("media", media)


def test_service_product_and_sku_ignore_stock_and_reject_adjustment():
    with TestClient(app) as client:
        token = _login(client)
        stores = client.get("/api/stores", headers=_headers(token)).json()
        local_store = next(item for item in stores if item["platform"] == "local")
        name = f"服务测试商品-{uuid.uuid4().hex[:6]}"
        created = client.post(
            "/api/products",
            headers=_headers(token),
            json={
                "store_id": local_store["id"],
                "name": name,
                "category": "除甲醛服务",
                "price_min": 45,
                "price_max": 68,
                "description": "服务测试商品",
                "skus": [
                    {
                        "spec_text": "套餐:测试治理, 计价单位:元/㎡",
                        "price": 45,
                        "stock": 5,
                        "warn_threshold": 10,
                    }
                ],
            },
        )
        assert created.status_code == 201, created.text
        product = created.json()
        assert product["is_service"] is True
        assert product["skus"][0]["stock"] == 9999
        assert product["skus"][0]["warn_threshold"] == 0
        assert product["skus"][0]["warning"] is False

        added = client.post(
            f"/api/products/{product['id']}/skus",
            headers=_headers(token),
            json={
                "spec_json": {"套餐": "补充套餐", "计价单位": "元/次"},
                "price": 99,
                "stock": 0,
                "warn_threshold": 10,
            },
        )
        assert added.status_code == 201, added.text
        assert added.json()["stock"] == 9999
        assert added.json()["warn_threshold"] == 0

        rejected = client.post(
            f"/api/skus/{added.json()['id']}/stock-adjust",
            headers=_headers(token),
            json={"change": 10, "reason": "manual"},
        )
        assert rejected.status_code == 400
        assert "服务套餐" in rejected.json()["detail"]
