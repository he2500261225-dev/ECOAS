from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine.worker import finish_running_attempts
from ..models import (
    CreativePlan,
    GenerationTask,
    ImageScheme,
    Product,
    TaskAttempt,
    VideoScript,
    utcnow,
)
from ..security import CurrentUser, DbSession
from ..services.settings import get_config

router = APIRouter(prefix="/api", tags=["tasks"])

SOURCE_TYPES = {"image_scheme", "video_script"}
ACTIVE_STATUSES = {"pending", "running"}


class TaskCreate(BaseModel):
    source_type: str
    source_id: int


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def attempt_view(attempt: TaskAttempt) -> dict:
    return {
        "id": attempt.id,
        "task_id": attempt.task_id,
        "attempt_no": attempt.attempt_no,
        "started_at": _iso(attempt.started_at),
        "finished_at": _iso(attempt.finished_at),
        "status": attempt.status,
        "error_message": attempt.error_message,
    }


def task_view(db: Session, task: GenerationTask) -> dict:
    source_title = ""
    plan_version: int | None = None
    if task.source_type == "image_scheme":
        scheme = db.get(ImageScheme, task.source_id)
        if scheme is not None:
            source_title = scheme.title
            plan = db.get(CreativePlan, scheme.plan_id)
            plan_version = plan.version if plan else None
    elif task.source_type == "video_script":
        script = db.get(VideoScript, task.source_id)
        if script is not None:
            source_title = script.title
            plan = db.get(CreativePlan, script.plan_id)
            plan_version = plan.version if plan else None

    attempts = db.scalars(
        select(TaskAttempt)
        .where(TaskAttempt.task_id == task.id)
        .order_by(TaskAttempt.attempt_no, TaskAttempt.id)
    ).all()
    payload = task.payload_json or {}
    result = payload.get("result") or {}

    return {
        "id": task.id,
        "product_id": task.product_id,
        "type": task.type,
        "source_type": task.source_type,
        "source_id": task.source_id,
        "source_title": source_title,
        "plan_version": plan_version,
        "payload_json": payload,
        "status": task.status,
        "attempt": task.attempt,
        "max_retry": task.max_retry,
        "timeout_seconds": task.timeout_seconds,
        "worker_id": task.worker_id,
        "heartbeat_at": _iso(task.heartbeat_at),
        "started_at": _iso(task.started_at),
        "finished_at": _iso(task.finished_at),
        "error_message": task.error_message,
        "result_asset_id": task.result_asset_id,
        "attachments": result.get("attachments") or [],
        "result_meta": result.get("meta") or {},
        "created_by": task.created_by,
        "created_at": _iso(task.created_at),
        "attempts": [attempt_view(item) for item in attempts],
    }


def _source_snapshot(db: Session, source_type: str, source_id: int) -> tuple[dict, str, int]:
    """返回 (快照 payload, 任务类型 image/video, 商品 ID)。"""
    if source_type == "image_scheme":
        scheme = db.get(ImageScheme, source_id)
        if scheme is None:
            raise HTTPException(status_code=404, detail="主图方案不存在")
        if scheme.status == "archived":
            raise HTTPException(status_code=400, detail="已归档方案不能生成素材")
        plan = db.get(CreativePlan, scheme.plan_id)
        product = db.get(Product, plan.product_id) if plan else None
        if plan is None or product is None:
            raise HTTPException(status_code=400, detail="方案关联的商品不存在")
        snapshot = {
            "product": {"id": product.id, "name": product.name},
            "plan_version": plan.version,
            "source": {
                "id": scheme.id,
                "title": scheme.title,
                "layout": scheme.layout,
                "copy": scheme.copy,
                "main_selling_point": scheme.main_selling_point,
                "visual_tip": scheme.visual_tip,
            },
        }
        return snapshot, "image", product.id

    if source_type == "video_script":
        script = db.scalar(
            select(VideoScript).where(VideoScript.id == source_id)
        )
        if script is None:
            raise HTTPException(status_code=404, detail="视频脚本不存在")
        if script.status == "archived":
            raise HTTPException(status_code=400, detail="已归档脚本不能生成素材")
        plan = db.get(CreativePlan, script.plan_id)
        product = db.get(Product, plan.product_id) if plan else None
        if plan is None or product is None:
            raise HTTPException(status_code=400, detail="脚本关联的商品不存在")
        snapshot = {
            "product": {"id": product.id, "name": product.name},
            "plan_version": plan.version,
            "source": {
                "id": script.id,
                "title": script.title,
                "hook_3s": script.hook_3s,
                "closing_cta": script.closing_cta,
                "shots": [
                    {
                        "shot_no": item.shot_no,
                        "duration_sec": item.duration_sec,
                        "scene_desc": item.scene_desc,
                        "voiceover": item.voiceover,
                        "cta_line": item.cta_line,
                    }
                    for item in script.shots
                ],
            },
        }
        return snapshot, "video", product.id

    raise HTTPException(status_code=400, detail="source_type 仅支持 image_scheme / video_script")


@router.post("/tasks", status_code=201)
def create_task(payload: TaskCreate, db: DbSession, user: CurrentUser):
    if payload.source_type not in SOURCE_TYPES:
        raise HTTPException(status_code=400, detail="source_type 仅支持 image_scheme / video_script")

    snapshot, task_type, product_id = _source_snapshot(
        db, payload.source_type, payload.source_id
    )
    media = get_config(db, "media")
    queue = get_config(db, "queue")
    timeout_key = "image_timeout" if task_type == "image" else "video_timeout"

    task = GenerationTask(
        product_id=product_id,
        type=task_type,
        source_type=payload.source_type,
        source_id=payload.source_id,
        payload_json=snapshot,
        status="pending",
        attempt=0,
        max_retry=max(0, int(queue.get("max_retry") or 0)),
        timeout_seconds=max(1, int(media.get(timeout_key) or 300)),
        created_by=user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_view(db, task)


@router.get("/tasks")
def list_tasks(
    db: DbSession,
    _: CurrentUser,
    product_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
):
    stmt = select(GenerationTask)
    if product_id is not None:
        stmt = stmt.where(GenerationTask.product_id == product_id)
    if status:
        stmt = stmt.where(GenerationTask.status == status)
    stmt = stmt.order_by(GenerationTask.created_at.desc(), GenerationTask.id.desc()).limit(
        max(1, min(200, limit))
    )
    tasks = db.scalars(stmt).all()
    return [task_view(db, task) for task in tasks]


@router.get("/tasks/{task_id}")
def get_task(task_id: int, db: DbSession, _: CurrentUser):
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task_view(db, task)


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, db: DbSession, _: CurrentUser):
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=400, detail="仅 pending / running 任务可取消")

    task.status = "cancelled"
    task.finished_at = utcnow()
    task.heartbeat_at = utcnow()
    finish_running_attempts(db, task.id, "cancelled")
    db.commit()
    db.refresh(task)
    return task_view(db, task)


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: int, db: DbSession, _: CurrentUser):
    task = db.get(GenerationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in {"failed", "timeout"}:
        raise HTTPException(status_code=400, detail="仅 failed / timeout 任务可重试")
    if int(task.attempt or 0) > int(task.max_retry or 0):
        raise HTTPException(status_code=400, detail="已达到最大重试次数")

    task.status = "pending"
    task.error_message = ""
    task.started_at = None
    task.finished_at = None
    task.heartbeat_at = None
    task.worker_id = None
    db.commit()
    db.refresh(task)
    return task_view(db, task)
