"""系统配置读取：统一合并默认值，供任务引擎与后续配置页复用。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SystemConfig

DEFAULT_CONFIGS: dict[str, dict] = {
    "media": {
        "image_timeout": 300,
        "video_timeout": 600,
        "delay_min": 3,
        "delay_max": 6,
        "fail_rate": 0.15,
    },
    "queue": {
        "concurrency": 2,
        "max_retry": 2,
        "heartbeat_seconds": 5,
        "sweep_seconds": 5,
    },
    "risk": {"high_risk_budget": 5000},
}


def get_config(db: Session, key: str) -> dict:
    """返回合并默认值后的配置副本，避免调用方误改数据库对象。"""
    defaults = dict(DEFAULT_CONFIGS.get(key) or {})
    row = db.scalar(select(SystemConfig).where(SystemConfig.key == key))
    if row is not None and isinstance(row.value_json, dict):
        defaults.update(row.value_json)
    return defaults
