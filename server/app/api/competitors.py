from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..models import Competitor, Product
from ..security import CurrentUser, DbSession
from ..services import llm

router = APIRouter(prefix="/api", tags=["competitors"])

PLATFORMS = {"taobao", "jd", "douyin", "pdd", "local"}


class CompetitorIn(BaseModel):
    platform: str = "taobao"
    name: str
    price: float = 0
    url: str = ""
    params_json: dict[str, str] = Field(default_factory=dict)
    sales_volume: int = 0
    rating: float = 0
    source: str = "manual"
    parse_status: str = "confirmed"


class CompetitorUpdate(BaseModel):
    platform: str | None = None
    name: str | None = None
    price: float | None = None
    url: str | None = None
    params_json: dict[str, str] | None = None
    sales_volume: int | None = None
    rating: float | None = None
    source: str | None = None
    parse_status: str | None = None


class ParseIn(BaseModel):
    text: str


def _validate_platform(platform: str) -> str:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台：{platform}")
    return platform


def competitor_view(competitor: Competitor) -> dict:
    return {
        "id": competitor.id,
        "product_id": competitor.product_id,
        "platform": competitor.platform,
        "name": competitor.name,
        "price": competitor.price,
        "url": competitor.url,
        "params_json": competitor.params_json or {},
        "sales_volume": competitor.sales_volume,
        "rating": competitor.rating,
        "source": competitor.source,
        "parse_status": competitor.parse_status,
        "created_at": competitor.created_at.isoformat(),
    }


def _apply_payload(competitor: Competitor, payload: CompetitorIn) -> None:
    competitor.platform = _validate_platform(payload.platform)
    competitor.name = payload.name.strip()
    competitor.price = float(payload.price)
    competitor.url = payload.url.strip()
    competitor.params_json = payload.params_json or {}
    competitor.sales_volume = int(payload.sales_volume)
    competitor.rating = float(payload.rating)
    competitor.source = payload.source if payload.source in {"manual", "ai_parse"} else "manual"
    competitor.parse_status = (
        payload.parse_status if payload.parse_status in {"draft", "confirmed"} else "confirmed"
    )


def _validate_competitor(payload: CompetitorIn) -> None:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="竞品名称不能为空")
    if payload.price < 0:
        raise HTTPException(status_code=400, detail="竞品价格不能为负数")
    if payload.sales_volume < 0:
        raise HTTPException(status_code=400, detail="销量不能为负数")
    if payload.rating < 0:
        raise HTTPException(status_code=400, detail="评分不能为负数")
    _validate_platform(payload.platform)


@router.get("/products/{product_id}/competitors")
def list_competitors(product_id: int, db: DbSession, _: CurrentUser):
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    rows = db.scalars(
        select(Competitor)
        .where(Competitor.product_id == product_id)
        .order_by(Competitor.price.asc(), Competitor.id)
    ).all()
    return [competitor_view(row) for row in rows]


@router.post("/products/{product_id}/competitors", status_code=201)
def create_competitor(
    product_id: int, payload: CompetitorIn, db: DbSession, _: CurrentUser
):
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    _validate_competitor(payload)
    competitor = Competitor(product_id=product_id)
    _apply_payload(competitor, payload)
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor_view(competitor)


@router.put("/competitors/{competitor_id}")
def update_competitor(
    competitor_id: int, payload: CompetitorUpdate, db: DbSession, _: CurrentUser
):
    competitor = db.get(Competitor, competitor_id)
    if competitor is None:
        raise HTTPException(status_code=404, detail="竞品不存在")

    data = competitor_view(competitor)
    data.pop("id", None)
    data.pop("product_id", None)
    data.pop("created_at", None)
    data.update(payload.model_dump(exclude_none=True))
    merged = CompetitorIn(**data)
    _validate_competitor(merged)
    _apply_payload(competitor, merged)
    db.commit()
    db.refresh(competitor)
    return competitor_view(competitor)


@router.delete("/competitors/{competitor_id}")
def delete_competitor(competitor_id: int, db: DbSession, _: CurrentUser):
    competitor = db.get(Competitor, competitor_id)
    if competitor is None:
        raise HTTPException(status_code=404, detail="竞品不存在")
    db.delete(competitor)
    db.commit()
    return {"ok": True, "message": "竞品已删除"}


@router.post("/products/{product_id}/competitors/parse")
def parse_competitor(
    product_id: int, payload: ParseIn, db: DbSession, _: CurrentUser
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="请粘贴需要解析的竞品文本")

    result = llm.generate_structured(
        db,
        "competitor_parse",
        {
            "text": text,
            "product": {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "price_min": product.price_min,
                "price_max": product.price_max,
            },
        },
    )
    drafts = result.content.get("drafts") or []
    return {
        "drafts": drafts,
        "channel": result.channel,
        "model": result.model,
        "note": result.note,
        "warnings": result.warnings,
    }
