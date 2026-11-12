"""SQLite 表队列 + 应用内 worker 线程。

状态机：
    pending -> running -> succeeded | failed | timeout
    pending / running -> cancelled
    failed / timeout -> retry（新 attempt）-> pending

- worker 线程数量由 system_configs["queue"].concurrency 决定；
- 运行中每 heartbeat_seconds 写一次心跳；
- 巡检线程回收心跳超过任务 timeout_seconds 的运行中任务；
- 成功任务自动写入 assets（pending_review）。
"""

from __future__ import annotations

import random
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Asset, GenerationTask, TaskAttempt, utcnow
from ..services.settings import get_config
from .generator import generate_media

_claim_lock = threading.Lock()


# ---------------------------------------------------------------------------
# 任务状态辅助
# ---------------------------------------------------------------------------


def finish_running_attempts(db: Session, task_id: int, status: str, error: str = "") -> None:
    attempts = db.scalars(
        select(TaskAttempt).where(
            TaskAttempt.task_id == task_id, TaskAttempt.status == "running"
        )
    ).all()
    for attempt in attempts:
        attempt.status = status
        attempt.finished_at = utcnow()
        attempt.error_message = error


def _mark_failed(db: Session, task: GenerationTask, message: str) -> None:
    task.status = "failed"
    task.error_message = message
    task.finished_at = utcnow()
    task.heartbeat_at = utcnow()
    finish_running_attempts(db, task.id, "failed", message)
    db.commit()


def claim_task(worker_id: str) -> int | None:
    """原子领取一个 pending 任务；同进程内用锁避免多 worker 抢同一条。"""
    with _claim_lock:
        with SessionLocal() as db:
            task = db.scalar(
                select(GenerationTask)
                .where(GenerationTask.status == "pending")
                .order_by(GenerationTask.created_at, GenerationTask.id)
            )
            if task is None:
                return None
            task.status = "running"
            task.worker_id = worker_id
            task.attempt = int(task.attempt or 0) + 1
            task.started_at = utcnow()
            task.heartbeat_at = utcnow()
            task.error_message = ""
            db.add(
                TaskAttempt(
                    task_id=task.id,
                    attempt_no=task.attempt,
                    started_at=utcnow(),
                    status="running",
                )
            )
            db.commit()
            return task.id


def execute_task(task_id: int, worker_id: str) -> None:
    """执行单个任务：模拟耗时 -> 按失败率判定 -> 生成素材入库。"""
    with SessionLocal() as db:
        task = db.get(GenerationTask, task_id)
        if task is None or task.status != "running":
            return

        media = get_config(db, "media")
        queue = get_config(db, "queue")
        delay_min = max(0.0, float(media.get("delay_min") or 0))
        delay_max = max(delay_min, float(media.get("delay_max") or delay_min))
        heartbeat_seconds = max(1, int(queue.get("heartbeat_seconds") or 5))
        fail_rate = min(1.0, max(0.0, float(media.get("fail_rate") or 0)))

        duration = random.uniform(delay_min, delay_max) if delay_max > 0 else 0.0
        started = time.monotonic()
        next_heartbeat = started + heartbeat_seconds

        while True:
            db.refresh(task)
            if task.status != "running":
                # 任务被取消（或巡检回收），不再产出素材
                finish_running_attempts(db, task.id, "cancelled")
                db.commit()
                return
            remaining = started + duration - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.2, remaining))
            if time.monotonic() >= next_heartbeat:
                task.heartbeat_at = utcnow()
                db.commit()
                next_heartbeat = time.monotonic() + heartbeat_seconds

        if random.random() < fail_rate:
            _mark_failed(
                db,
                task,
                "模拟生成失败：媒体服务返回异常（由失败率配置注入），可重试",
            )
            return

        try:
            result = generate_media(db, task)
        except Exception as exc:  # 生成器内部异常按失败处理，保留 attempt 记录
            _mark_failed(db, task, f"素材生成失败：{exc}")
            return

        db.refresh(task)
        if task.status != "running":
            db.rollback()
            with SessionLocal() as cleanup:
                finish_running_attempts(cleanup, task_id, "cancelled")
                cleanup.commit()
            return

        asset = Asset(**result["asset"])
        db.add(asset)
        db.flush()

        payload = dict(task.payload_json or {})
        payload["result"] = {
            "attachments": result.get("attachments") or [],
            "meta": result.get("meta") or {},
            "asset_id": asset.id,
        }
        task.payload_json = payload
        task.status = "succeeded"
        task.result_asset_id = asset.id
        task.finished_at = utcnow()
        task.heartbeat_at = utcnow()
        task.error_message = ""
        finish_running_attempts(db, task.id, "succeeded")
        db.commit()


def sweep_timeouts() -> int:
    """巡检运行中任务，心跳超时则标记 timeout。返回回收数量。"""
    now = utcnow()
    recovered = 0
    with SessionLocal() as db:
        tasks = db.scalars(
            select(GenerationTask).where(GenerationTask.status == "running")
        ).all()
        for task in tasks:
            reference = task.heartbeat_at or task.started_at or task.created_at
            if reference is None:
                continue
            if (now - reference).total_seconds() <= max(1, int(task.timeout_seconds or 1)):
                continue
            task.status = "timeout"
            task.error_message = f"任务心跳超时（阈值 {task.timeout_seconds}s），已由巡检线程回收"
            task.finished_at = now
            finish_running_attempts(db, task.id, "timeout", task.error_message)
            recovered += 1
        db.commit()
    return recovered


# ---------------------------------------------------------------------------
# worker 线程池
# ---------------------------------------------------------------------------


class TaskWorkerPool:
    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._started = False
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._stop.clear()
            try:
                with SessionLocal() as db:
                    queue = get_config(db, "queue")
                concurrency = max(1, min(8, int(queue.get("concurrency") or 1)))
                sweep_seconds = max(1, int(queue.get("sweep_seconds") or 5))
            except Exception:
                concurrency, sweep_seconds = 1, 5

            for index in range(concurrency):
                thread = threading.Thread(
                    target=self._worker_loop,
                    name=f"ecoa-worker-{index + 1}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

            sweeper = threading.Thread(
                target=self._sweep_loop,
                args=(sweep_seconds,),
                name="ecoa-sweeper",
                daemon=True,
            )
            sweeper.start()
            self._threads.append(sweeper)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._stop.set()
            for thread in self._threads:
                thread.join(timeout=2)
            self._threads = []
            self._started = False

    def _worker_loop(self) -> None:
        worker_id = threading.current_thread().name
        while not self._stop.is_set():
            task_id = None
            try:
                task_id = claim_task(worker_id)
            except Exception:
                self._stop.wait(1)
                continue
            if task_id is None:
                self._stop.wait(0.5)
                continue
            try:
                execute_task(task_id, worker_id)
            except Exception as exc:
                # 兜底：任何未预期异常都不能让 worker 退出
                with SessionLocal() as db:
                    task = db.get(GenerationTask, task_id)
                    if task is not None and task.status == "running":
                        _mark_failed(db, task, f"任务执行异常：{exc}")

    def _sweep_loop(self, interval: int) -> None:
        while not self._stop.wait(interval):
            try:
                sweep_timeouts()
            except Exception:
                continue


worker_pool = TaskWorkerPool()
