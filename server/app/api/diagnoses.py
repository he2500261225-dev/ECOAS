from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..models import Competitor, Diagnosis, Product, ReviewReport, Sku
from ..security import CurrentUser, DbSession
from ..services import llm
from ..services.service_profiles import service_context

router = APIRouter(prefix="/api", tags=["diagnoses"])


class GenerateIn(BaseModel):
    source_report_id: int | None = None


class DiagnosisUpdate(BaseModel):
    content_json: dict


def _channel_from_model(model: str) -> str:
    lowered = (model or "").lower()
    if "fallback" in lowered:
        return "mock_fallback"
    if lowered.startswith("mock"):
        return "mock"
    return "real"


def diagnosis_view(diagnosis: Diagnosis) -> dict:
    return {
        "id": diagnosis.id,
        "product_id": diagnosis.product_id,
        "version": diagnosis.version,
        "status": diagnosis.status,
        "content_json": diagnosis.content_json or {},
        "source_report_id": diagnosis.source_report_id,
        "model": diagnosis.model,
        "channel": _channel_from_model(diagnosis.model),
        "created_by": diagnosis.created_by,
        "created_at": diagnosis.created_at.isoformat(),
        "updated_at": diagnosis.updated_at.isoformat(),
    }


def _build_context(db, product: Product, source_report: ReviewReport | None) -> dict:
    skus = db.scalars(
        select(Sku).where(Sku.product_id == product.id).order_by(Sku.id)
    ).all()
    competitors = db.scalars(
        select(Competitor).where(Competitor.product_id == product.id).order_by(Competitor.id)
    ).all()
    action_items: list[str] = []
    previous_conclusion: dict | None = None
    if source_report is not None:
        structured = source_report.structured_json or {}
        action_items = [str(item) for item in (structured.get("action_items") or [])]
        attribution = structured.get("attribution")
        metric_comparison = structured.get("metric_comparison")
    else:
        attribution = None
        metric_comparison = None

    current = db.scalar(
        select(Diagnosis).where(
            Diagnosis.product_id == product.id, Diagnosis.status == "current"
        )
    )
    if current is not None:
        previous_conclusion = current.content_json or {}

    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price_min": product.price_min,
            "price_max": product.price_max,
            "description": product.description,
        },
        "service_profile": service_context(product.category),
        "skus": [
            {
                "id": sku.id,
                "spec_json": sku.spec_json,
                "price": sku.price,
                "stock": sku.stock,
                "warn_threshold": sku.warn_threshold,
            }
            for sku in skus
        ],
        "competitors": [
            {
                "id": item.id,
                "name": item.name,
                "platform": item.platform,
                "price": item.price,
                "params_json": item.params_json or {},
                "sales_volume": item.sales_volume,
                "rating": item.rating,
            }
            for item in competitors
        ],
        "action_items": action_items,
        "previous_conclusion": previous_conclusion,
        "report_attribution": attribution,
        "metric_comparison": metric_comparison,
    }


@router.post("/products/{product_id}/diagnoses/generate")
def generate_diagnosis(
    product_id: int,
    payload: GenerateIn,
    db: DbSession,
    user: CurrentUser,
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    source_report = None
    if payload.source_report_id is not None:
        source_report = db.get(ReviewReport, payload.source_report_id)
        if source_report is None:
            raise HTTPException(status_code=404, detail="复盘报告不存在")
        if source_report.product_id != product.id:
            raise HTTPException(status_code=400, detail="复盘报告不属于该商品")

    context = _build_context(db, product, source_report)
    result = llm.generate_structured(db, "diagnosis", context)

    next_version = (
        db.scalar(select(func.max(Diagnosis.version)).where(Diagnosis.product_id == product.id))
        or 0
    ) + 1

    for old in db.scalars(
        select(Diagnosis).where(
            Diagnosis.product_id == product.id, Diagnosis.status == "current"
        )
    ).all():
        old.status = "history"

    diagnosis = Diagnosis(
        product_id=product.id,
        version=next_version,
        status="current",
        content_json=result.content,
        source_report_id=payload.source_report_id,
        model=result.model,
        created_by=user.id,
    )
    db.add(diagnosis)
    db.commit()
    db.refresh(diagnosis)

    data = diagnosis_view(diagnosis)
    data["generate_channel"] = result.channel
    data["note"] = result.note
    data["warnings"] = result.warnings
    return data


@router.get("/products/{product_id}/diagnoses")
def list_diagnoses(product_id: int, db: DbSession, _: CurrentUser):
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    rows = db.scalars(
        select(Diagnosis)
        .where(Diagnosis.product_id == product_id)
        .order_by(Diagnosis.version.desc())
    ).all()
    return [diagnosis_view(row) for row in rows]


@router.get("/diagnoses/{diagnosis_id}")
def get_diagnosis(diagnosis_id: int, db: DbSession, _: CurrentUser):
    diagnosis = db.get(Diagnosis, diagnosis_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="诊断不存在")
    return diagnosis_view(diagnosis)


@router.put("/diagnoses/{diagnosis_id}")
def update_diagnosis(
    diagnosis_id: int, payload: DiagnosisUpdate, db: DbSession, _: CurrentUser
):
    diagnosis = db.get(Diagnosis, diagnosis_id)
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="诊断不存在")
    if diagnosis.status != "current":
        raise HTTPException(status_code=400, detail="仅可编辑当前版本诊断")

    try:
        validated = llm.validate_content("diagnosis", payload.content_json)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"诊断内容校验失败：{exc}") from exc

    diagnosis.content_json = validated
    db.commit()
    db.refresh(diagnosis)
    return diagnosis_view(diagnosis)
