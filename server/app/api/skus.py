from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..models import PlatformSkuMapping, Product, Sku, StockFlow, User
from ..security import CurrentUser, DbSession
from ..services.service_profiles import is_service_category

router = APIRouter(prefix="/api", tags=["skus"])

PLATFORMS = {"taobao", "jd", "douyin", "pdd", "local"}

SERVICE_SKU_STOCK = 9999
SERVICE_SKU_WARN_THRESHOLD = 0


class SkuCreate(BaseModel):
    spec_json: dict[str, str]
    price: float = 0
    stock: int = 0
    warn_threshold: int = 10


class SkuUpdate(BaseModel):
    spec_json: dict[str, str] | None = None
    price: float | None = None
    warn_threshold: int | None = None


class StockAdjust(BaseModel):
    change: int
    reason: str = "manual"


class MappingCreate(BaseModel):
    platform: str
    platform_spec_name: str = ""
    platform_price: float | None = None
    platform_sku_code: str = ""


class MappingUpdate(BaseModel):
    platform: str | None = None
    platform_spec_name: str | None = None
    platform_price: float | None = None
    platform_sku_code: str | None = None


def _sku_or_404(db, sku_id: int) -> Sku:
    sku = db.scalar(select(Sku).options(selectinload(Sku.mappings)).where(Sku.id == sku_id))
    if sku is None:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    return sku


def _mapping_view(mapping: PlatformSkuMapping) -> dict:
    return {
        "id": mapping.id,
        "sku_id": mapping.sku_id,
        "platform": mapping.platform,
        "platform_spec_name": mapping.platform_spec_name,
        "platform_price": mapping.platform_price,
        "platform_sku_code": mapping.platform_sku_code,
    }


def _validate_platform(platform: str) -> str:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台：{platform}")
    return platform


@router.post("/products/{product_id}/skus", status_code=201)
def create_sku(product_id: int, payload: SkuCreate, db: DbSession, _: CurrentUser):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    if not payload.spec_json:
        raise HTTPException(status_code=400, detail="SKU 规格不能为空")
    if payload.price < 0:
        raise HTTPException(status_code=400, detail="售价不能为负数")
    is_service = is_service_category(product.category)
    if not is_service and (payload.stock < 0 or payload.warn_threshold < 0):
        raise HTTPException(status_code=400, detail="库存与安全库存不能为负数")

    sku = Sku(
        product_id=product_id,
        spec_json=payload.spec_json,
        price=float(payload.price),
        stock=SERVICE_SKU_STOCK if is_service else int(payload.stock),
        warn_threshold=SERVICE_SKU_WARN_THRESHOLD if is_service else int(payload.warn_threshold),
    )
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return _mapping_sku_view(sku)


def _mapping_sku_view(sku: Sku) -> dict:
    return {
        "id": sku.id,
        "spec": sku.spec_json,
        "price": sku.price,
        "stock": sku.stock,
        "warn_threshold": sku.warn_threshold,
        "warning": sku.stock <= sku.warn_threshold,
        "mappings": [_mapping_view(m) for m in sku.mappings],
    }


@router.put("/skus/{sku_id}")
def update_sku(sku_id: int, payload: SkuUpdate, db: DbSession, _: CurrentUser):
    sku = _sku_or_404(db, sku_id)
    product = db.get(Product, sku.product_id)
    is_service = is_service_category(product.category if product else None)
    if payload.spec_json is not None:
        if not payload.spec_json:
            raise HTTPException(status_code=400, detail="SKU 规格不能为空")
        sku.spec_json = payload.spec_json
    if payload.price is not None:
        if payload.price < 0:
            raise HTTPException(status_code=400, detail="售价不能为负数")
        sku.price = float(payload.price)
    if payload.warn_threshold is not None:
        if payload.warn_threshold < 0:
            raise HTTPException(status_code=400, detail="安全库存不能为负数")
        sku.warn_threshold = (
            SERVICE_SKU_WARN_THRESHOLD if is_service else int(payload.warn_threshold)
        )
    if is_service:
        sku.warn_threshold = SERVICE_SKU_WARN_THRESHOLD
    db.commit()
    db.refresh(sku)
    return _mapping_sku_view(sku)


@router.delete("/skus/{sku_id}")
def delete_sku(sku_id: int, db: DbSession, _: CurrentUser):
    sku = _sku_or_404(db, sku_id)
    if sku.mappings:
        for mapping in list(sku.mappings):
            db.delete(mapping)
    for flow in db.scalars(select(StockFlow).where(StockFlow.sku_id == sku_id)).all():
        db.delete(flow)
    product = db.get(Product, sku.product_id)
    if product and product.main_sku_id == sku.id:
        remaining = db.scalars(
            select(Sku).where(Sku.product_id == sku.product_id, Sku.id != sku.id)
        ).first()
        product.main_sku_id = remaining.id if remaining else None
    db.delete(sku)
    db.commit()
    return {"ok": True, "message": "SKU 已删除"}


@router.post("/skus/{sku_id}/stock-adjust")
def adjust_stock(sku_id: int, payload: StockAdjust, db: DbSession, user: CurrentUser):
    sku = _sku_or_404(db, sku_id)
    product = db.get(Product, sku.product_id)
    if is_service_category(product.category if product else None):
        raise HTTPException(status_code=400, detail="服务套餐不参与库存调整与流水")
    if payload.change == 0:
        raise HTTPException(status_code=400, detail="库存调整数量不能为 0")
    next_stock = sku.stock + int(payload.change)
    if next_stock < 0:
        raise HTTPException(
            status_code=400,
            detail=f"调整后库存不能为负数（当前库存 {sku.stock}）",
        )
    sku.stock = next_stock
    flow = StockFlow(
        sku_id=sku.id,
        change=int(payload.change),
        reason=(payload.reason or "manual").strip()[:50],
        stock_after=next_stock,
        operator_id=user.id,
    )
    db.add(flow)
    db.commit()
    db.refresh(sku)
    db.refresh(flow)
    return {
        "sku": _mapping_sku_view(sku),
        "flow": {
            "id": flow.id,
            "sku_id": flow.sku_id,
            "change": flow.change,
            "reason": flow.reason,
            "stock_after": flow.stock_after,
            "operator_id": flow.operator_id,
            "operator_name": user.display_name,
            "created_at": flow.created_at.isoformat(),
        },
    }


@router.get("/skus/{sku_id}/stock-flows")
def list_stock_flows(sku_id: int, db: DbSession, _: CurrentUser):
    _sku_or_404(db, sku_id)
    rows = db.execute(
        select(StockFlow, User)
        .outerjoin(User, User.id == StockFlow.operator_id)
        .where(StockFlow.sku_id == sku_id)
        .order_by(StockFlow.created_at.desc(), StockFlow.id.desc())
    ).all()
    return [
        {
            "id": flow.id,
            "sku_id": flow.sku_id,
            "change": flow.change,
            "reason": flow.reason,
            "stock_after": flow.stock_after,
            "operator_id": flow.operator_id,
            "operator_name": user.display_name if user else "",
            "created_at": flow.created_at.isoformat(),
        }
        for flow, user in rows
    ]


@router.get("/skus/{sku_id}/mappings")
def list_mappings(sku_id: int, db: DbSession, _: CurrentUser):
    sku = _sku_or_404(db, sku_id)
    return [_mapping_view(mapping) for mapping in sku.mappings]


@router.post("/skus/{sku_id}/mappings", status_code=201)
def create_mapping(sku_id: int, payload: MappingCreate, db: DbSession, _: CurrentUser):
    sku = _sku_or_404(db, sku_id)
    _validate_platform(payload.platform)
    if payload.platform_sku_code:
        exists = db.scalar(
            select(PlatformSkuMapping).where(
                PlatformSkuMapping.platform == payload.platform,
                PlatformSkuMapping.platform_sku_code == payload.platform_sku_code,
            )
        )
        if exists:
            raise HTTPException(status_code=400, detail="该平台 SKU 编码已被映射")
    mapping = PlatformSkuMapping(
        sku_id=sku.id,
        platform=payload.platform,
        platform_spec_name=payload.platform_spec_name or " / ".join(str(v) for v in sku.spec_json.values()),
        platform_price=float(payload.platform_price if payload.platform_price is not None else sku.price),
        platform_sku_code=payload.platform_sku_code.strip(),
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return _mapping_view(mapping)


@router.put("/mappings/{mapping_id}")
def update_mapping(mapping_id: int, payload: MappingUpdate, db: DbSession, _: CurrentUser):
    mapping = db.get(PlatformSkuMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="平台映射不存在")

    next_platform = payload.platform if payload.platform is not None else mapping.platform
    _validate_platform(next_platform)
    next_code = (
        payload.platform_sku_code.strip()
        if payload.platform_sku_code is not None
        else mapping.platform_sku_code
    )
    if next_code:
        duplicate = db.scalar(
            select(PlatformSkuMapping).where(
                PlatformSkuMapping.platform == next_platform,
                PlatformSkuMapping.platform_sku_code == next_code,
                PlatformSkuMapping.id != mapping.id,
            )
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="该平台 SKU 编码已被映射")

    mapping.platform = next_platform
    if payload.platform_spec_name is not None:
        mapping.platform_spec_name = payload.platform_spec_name
    if payload.platform_price is not None:
        if payload.platform_price < 0:
            raise HTTPException(status_code=400, detail="平台售价不能为负数")
        mapping.platform_price = float(payload.platform_price)
    mapping.platform_sku_code = next_code
    db.commit()
    db.refresh(mapping)
    return _mapping_view(mapping)


@router.delete("/mappings/{mapping_id}")
def delete_mapping(mapping_id: int, db: DbSession, _: CurrentUser):
    mapping = db.get(PlatformSkuMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="平台映射不存在")
    db.delete(mapping)
    db.commit()
    return {"ok": True, "message": "平台映射已删除"}
