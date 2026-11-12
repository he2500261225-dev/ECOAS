from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from ..models import (
    Asset,
    CreativePlan,
    Diagnosis,
    MetricRecord,
    Placement,
    ReviewReport,
)

STAGE_LABELS = {
    "draft": "建档中",
    "diagnosed": "已诊断",
    "creative_ready": "创意就绪",
    "asset_ready": "素材就绪",
    "launching": "投放中",
    "reviewing": "复盘中",
    "reviewed": "已闭环",
}


def product_stage(db: Session, product_id: int) -> str:
    """按业务闭环的推进程度派生单品阶段，越靠后优先级越高。"""
    has_report = db.scalar(
        select(exists().where(ReviewReport.product_id == product_id))
    )
    if has_report:
        return "reviewed"

    has_metrics = db.scalar(select(exists().where(MetricRecord.product_id == product_id)))
    if has_metrics:
        return "reviewing"

    has_approved_placement = db.scalar(
        select(
            exists().where(
                Placement.product_id == product_id,
                Placement.status.in_(["approved", "closed"]),
            )
        )
    )
    if has_approved_placement:
        return "launching"

    has_approved_asset = db.scalar(
        select(
            exists().where(
                Asset.product_id == product_id,
                Asset.status == "approved",
            )
        )
    )
    if has_approved_asset:
        return "asset_ready"

    has_plan = db.scalar(
        select(exists().where(CreativePlan.product_id == product_id))
    )
    if has_plan:
        return "creative_ready"

    has_diagnosis = db.scalar(
        select(
            exists().where(
                Diagnosis.product_id == product_id,
                Diagnosis.status == "current",
            )
        )
    )
    if has_diagnosis:
        return "diagnosed"

    return "draft"
