import time
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import ASSET_DIR
from app.db import SessionLocal
from app.engine.worker import sweep_timeouts
from app.main import app
from app.models import GenerationTask, SystemConfig, TaskAttempt, utcnow


def _login(client: TestClient, username: str = "operator") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


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


def _create_product(client: TestClient, token: str, with_diagnosis: bool = True) -> dict:
    stores = client.get("/api/stores", headers=_headers(token)).json()
    resp = client.post(
        "/api/products",
        headers=_headers(token),
        json={
            "store_id": stores[0]["id"],
            "name": _unique("M3 测试防晒衣"),
            "category": "防晒服饰",
            "description": "原纱型冰丝面料，UPF50+ 防晒，凉感透气，适合通勤与轻户外。",
            "skus": [
                {
                    "spec_text": "颜色:雾霾蓝,尺码:M",
                    "price": 149,
                    "stock": 60,
                    "warn_threshold": 10,
                },
                {
                    "spec_text": "颜色:月光白,尺码:L",
                    "price": 159,
                    "stock": 30,
                    "warn_threshold": 10,
                },
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    product = resp.json()
    if with_diagnosis:
        diag = client.post(
            f"/api/products/{product['id']}/diagnoses/generate",
            headers=_headers(token),
            json={},
        )
        assert diag.status_code == 200, diag.text
    return product


def _generate_plan(client: TestClient, token: str, product_id: int) -> dict:
    resp = client.post(
        f"/api/products/{product_id}/creative-plans/generate",
        headers=_headers(token),
        json={},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _wait_task(
    client: TestClient, token: str, task_id: int, statuses: set[str], timeout: float = 10.0
) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/api/tasks/{task_id}", headers=_headers(token))
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in statuses:
            return last
        time.sleep(0.05)
    raise AssertionError(f"任务未在 {timeout}s 内进入 {statuses}，最后状态：{last}")


def _create_task(client: TestClient, token: str, source_type: str, source_id: int) -> dict:
    resp = client.post(
        "/api/tasks",
        headers=_headers(token),
        json={"source_type": source_type, "source_id": source_id},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_creative_plan_generation_editing_and_versioning():
    with TestClient(app) as client:
        token = _login(client)
        no_diag_product = _create_product(client, token, with_diagnosis=False)
        blocked = client.post(
            f"/api/products/{no_diag_product['id']}/creative-plans/generate",
            headers=_headers(token),
            json={},
        )
        assert blocked.status_code == 400
        assert "诊断" in blocked.json()["detail"]

        product = _create_product(client, token)
        plan = _generate_plan(client, token, product["id"])
        assert plan["version"] == 1
        assert plan["generate_channel"] == "mock"
        assert len(plan["image_schemes"]) >= 3
        assert len(plan["video_scripts"]) >= 3
        for scheme in plan["image_schemes"]:
            for field in ("title", "layout", "copy", "main_selling_point", "visual_tip"):
                assert scheme[field].strip()
        for script in plan["video_scripts"]:
            assert script["hook_3s"].strip()
            assert script["closing_cta"].strip()
            assert len(script["shots"]) >= 4
            for shot in script["shots"]:
                assert shot["scene_desc"].strip()
                assert shot["duration_sec"] >= 1

        scheme = plan["image_schemes"][0]
        edited = client.put(
            f"/api/image-schemes/{scheme['id']}",
            headers=_headers(token),
            json={"copy": "人工修订后的主图文案", "title": "人工修订方案"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["copy"] == "人工修订后的主图文案"
        assert edited.json()["title"] == "人工修订方案"

        confirmed = client.post(
            f"/api/image-schemes/{scheme['id']}/confirm", headers=_headers(token)
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "confirmed"

        archived = client.post(
            f"/api/image-schemes/{scheme['id']}/archive", headers=_headers(token)
        )
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"

        archived_edit = client.put(
            f"/api/image-schemes/{scheme['id']}",
            headers=_headers(token),
            json={"copy": "归档后不可修改"},
        )
        assert archived_edit.status_code == 400

        script = plan["video_scripts"][0]
        assert len(script["shots"]) >= 4
        script_edit = client.put(
            f"/api/video-scripts/{script['id']}",
            headers=_headers(token),
            json={"hook_3s": "人工改写的 3 秒钩子"},
        )
        assert script_edit.status_code == 200
        assert script_edit.json()["hook_3s"] == "人工改写的 3 秒钩子"

        script_confirm = client.post(
            f"/api/video-scripts/{script['id']}/confirm", headers=_headers(token)
        )
        assert script_confirm.status_code == 200
        assert script_confirm.json()["status"] == "confirmed"

        added = client.post(
            f"/api/video-scripts/{script['id']}/shots",
            headers=_headers(token),
            json={
                "duration_sec": 5,
                "scene_desc": "新增分镜：展示使用细节",
                "voiceover": "这一处细节，决定了体验上限",
                "cta_line": "细节见真章",
            },
        )
        assert added.status_code == 201, added.text
        assert added.json()["shot_no"] == len(script["shots"]) + 1

        plans_after = client.get(
            f"/api/products/{product['id']}/creative-plans", headers=_headers(token)
        ).json()
        script_after = next(
            item
            for item in plans_after[0]["video_scripts"]
            if item["id"] == script["id"]
        )
        assert script_after["status"] == "draft"  # 分镜变更后需要重新确认

        shot = added.json()
        shot_edit = client.put(
            f"/api/video-shots/{shot['id']}",
            headers=_headers(token),
            json={"scene_desc": "人工修订分镜描述"},
        )
        assert shot_edit.status_code == 200
        assert shot_edit.json()["scene_desc"] == "人工修订分镜描述"

        removed = client.delete(f"/api/video-shots/{shot['id']}", headers=_headers(token))
        assert removed.status_code == 200

        second = _generate_plan(client, token, product["id"])
        assert second["version"] == 2
        plans = client.get(
            f"/api/products/{product['id']}/creative-plans", headers=_headers(token)
        ).json()
        assert [item["version"] for item in plans] == [2, 1]


def test_image_task_success_creates_reviewable_asset():
    media = _snapshot_config("media")
    try:
        _set_config("media", {"delay_min": 0, "delay_max": 0, "fail_rate": 0.0})
        with TestClient(app) as client:
            token = _login(client)
            product = _create_product(client, token)
            plan = _generate_plan(client, token, product["id"])
            scheme = plan["image_schemes"][0]

            task = _create_task(client, token, "image_scheme", scheme["id"])
            assert task["status"] == "pending"
            assert task["type"] == "image"
            assert task["payload_json"]["source"]["title"] == scheme["title"]

            done = _wait_task(client, token, task["id"], {"succeeded"})
            assert done["result_asset_id"]
            assert len(done["attempts"]) == 1
            assert done["attempts"][0]["status"] == "succeeded"
            assert done["finished_at"]

            assets = client.get(
                f"/api/products/{product['id']}/assets?type=image", headers=_headers(token)
            ).json()
            asset = next(item for item in assets if item["id"] == done["result_asset_id"])
            assert asset["status"] == "pending_review"
            assert asset["file_path"].startswith("/files/assets/")
            assert (ASSET_DIR / asset["filename"]).exists()

            file_resp = client.get(asset["file_path"])
            assert file_resp.status_code == 200
            assert "<svg" in file_resp.text

            review = client.post(
                f"/api/assets/{asset['id']}/review",
                headers=_headers(token),
                json={"action": "approve", "note": "构图与卖点表达清晰，可投放。"},
            )
            assert review.status_code == 200, review.text
            assert review.json()["status"] == "approved"
            assert review.json()["reviewed_by_name"]

            stage = client.get(f"/api/products/{product['id']}", headers=_headers(token)).json()
            assert stage["stage"] == "asset_ready"

            tags = client.put(
                f"/api/assets/{asset['id']}/tags",
                headers=_headers(token),
                json={"tags": ["通勤场景", "主图", "通勤场景"]},
            )
            assert tags.status_code == 200
            assert tags.json()["tags_json"] == ["通勤场景", "主图"]

            again = client.post(
                f"/api/assets/{asset['id']}/review",
                headers=_headers(token),
                json={"action": "approve", "note": ""},
            )
            assert again.status_code == 400

            archived = client.post(
                f"/api/assets/{asset['id']}/archive", headers=_headers(token)
            )
            assert archived.status_code == 200
            assert archived.json()["status"] == "archived"
    finally:
        _restore_config("media", media)


def test_task_failure_retry_and_retry_limit():
    media = _snapshot_config("media")
    queue = _snapshot_config("queue")
    try:
        _set_config("media", {"delay_min": 0, "delay_max": 0, "fail_rate": 1.0})
        with TestClient(app) as client:
            token = _login(client)
            product = _create_product(client, token)
            plan = _generate_plan(client, token, product["id"])
            scheme = plan["image_schemes"][1]

            task = _create_task(client, token, "image_scheme", scheme["id"])
            failed = _wait_task(client, token, task["id"], {"failed"})
            assert failed["attempts"][0]["status"] == "failed"
            assert failed["error_message"]
            assert failed["result_asset_id"] is None

            _set_config("media", {"fail_rate": 0.0})
            retried = client.post(
                f"/api/tasks/{task['id']}/retry", headers=_headers(token)
            )
            assert retried.status_code == 200, retried.text
            assert retried.json()["status"] == "pending"

            succeeded = _wait_task(client, token, task["id"], {"succeeded"})
            statuses = [item["status"] for item in succeeded["attempts"]]
            assert statuses == ["failed", "succeeded"]
            assert succeeded["attempt"] == 2
            assert succeeded["result_asset_id"]

            not_retryable = client.post(
                f"/api/tasks/{task['id']}/retry", headers=_headers(token)
            )
            assert not_retryable.status_code == 400

            # 最大重试次数为 0 时，失败任务不可重试
            _set_config("queue", {"max_retry": 0})
            _set_config("media", {"fail_rate": 1.0})
            limited = _create_task(client, token, "image_scheme", plan["image_schemes"][2]["id"])
            limited_failed = _wait_task(client, token, limited["id"], {"failed"})
            assert limited_failed["max_retry"] == 0
            denied = client.post(
                f"/api/tasks/{limited['id']}/retry", headers=_headers(token)
            )
            assert denied.status_code == 400
            assert "最大重试" in denied.json()["detail"]
    finally:
        _restore_config("media", media)
        _restore_config("queue", queue)


def test_task_cancel_and_timeout_sweep():
    media = _snapshot_config("media")
    try:
        _set_config("media", {"delay_min": 3, "delay_max": 3, "fail_rate": 0.0})
        with TestClient(app) as client:
            token = _login(client)
            product = _create_product(client, token)
            plan = _generate_plan(client, token, product["id"])
            scheme = plan["image_schemes"][0]

            task = _create_task(client, token, "image_scheme", scheme["id"])
            running = _wait_task(client, token, task["id"], {"running"})
            assert running["started_at"]

            cancelled = client.post(
                f"/api/tasks/{task['id']}/cancel", headers=_headers(token)
            )
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"

            time.sleep(0.8)
            after = client.get(f"/api/tasks/{task['id']}", headers=_headers(token)).json()
            assert after["status"] == "cancelled"
            assert after["result_asset_id"] is None
            assert after["attempts"][-1]["status"] == "cancelled"

            other = client.post(
                f"/api/tasks/{task['id']}/cancel", headers=_headers(token)
            )
            assert other.status_code == 400

            # 直接构造一个心跳超时的 running 任务，验证巡检回收
            with SessionLocal() as db:
                stale = GenerationTask(
                    product_id=product["id"],
                    type="image",
                    source_type="image_scheme",
                    source_id=scheme["id"],
                    payload_json={},
                    status="running",
                    attempt=1,
                    max_retry=2,
                    timeout_seconds=1,
                    started_at=utcnow() - timedelta(seconds=30),
                    heartbeat_at=utcnow() - timedelta(seconds=30),
                )
                db.add(stale)
                db.flush()
                db.add(
                    TaskAttempt(
                        task_id=stale.id,
                        attempt_no=1,
                        started_at=utcnow() - timedelta(seconds=30),
                        status="running",
                    )
                )
                db.commit()
                stale_id = stale.id

            sweep_timeouts()
            timed_out = client.get(f"/api/tasks/{stale_id}", headers=_headers(token)).json()
            assert timed_out["status"] == "timeout"
            assert timed_out["attempts"][-1]["status"] == "timeout"

            _set_config("media", {"delay_min": 0, "delay_max": 0})
            recovered = client.post(
                f"/api/tasks/{stale_id}/retry", headers=_headers(token)
            )
            assert recovered.status_code == 200
            repaired = _wait_task(client, token, stale_id, {"succeeded"})
            assert repaired["result_asset_id"]
    finally:
        _restore_config("media", media)


def test_video_task_writes_preview_and_script_attachments():
    media = _snapshot_config("media")
    try:
        _set_config("media", {"delay_min": 0, "delay_max": 0, "fail_rate": 0.0})
        with TestClient(app) as client:
            token = _login(client)
            product = _create_product(client, token)
            plan = _generate_plan(client, token, product["id"])
            script = plan["video_scripts"][0]

            task = _create_task(client, token, "video_script", script["id"])
            assert task["type"] == "video"
            done = _wait_task(client, token, task["id"], {"succeeded"})

            assets = client.get(
                f"/api/products/{product['id']}/assets?type=video", headers=_headers(token)
            ).json()
            asset = next(item for item in assets if item["id"] == done["result_asset_id"])
            assert asset["status"] == "pending_review"
            assert (ASSET_DIR / asset["filename"]).exists()

            attachments = done["attachments"]
            assert {item["kind"] for item in attachments} == {"script_json", "script_markdown"}
            for item in attachments:
                resp = client.get(item["url"])
                assert resp.status_code == 200
                assert len(resp.text) > 20

            json_attachment = next(item for item in attachments if item["kind"] == "script_json")
            payload = client.get(json_attachment["url"]).json()
            assert len(payload["shots"]) == len(script["shots"])
            assert payload["script"]["title"] == script["title"]
    finally:
        _restore_config("media", media)
