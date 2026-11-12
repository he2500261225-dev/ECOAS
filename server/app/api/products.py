from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..models import (
    Asset,
    PlatformSkuMapping,
    Product,
    Sku,
    Store,
)
from ..security import CurrentUser, DbSession
from ..services.lifecycle import STAGE_LABELS, product_stage
from ..services.service_profiles import is_service_category, price_unit_for

router = APIRouter(prefix="/api/products", tags=["products"])

PLATFORMS = {"taobao", "jd", "douyin", "pdd", "local"}

SERVICE_SKU_STOCK = 9999
SERVICE_SKU_WARN_THRESHOLD = 0


class MappingIn(BaseModel):
    platform: str | None = None
    platform_spec_name: str = ""
    platform_price: float | None = None
    platform_sku_code: str = ""


class SkuIn(BaseModel):
    spec_json: dict[str, str] | None = None
    spec_text: str | None = None
    price: float = 0
    stock: int = 0
    warn_threshold: int = 10
    mappings: list[MappingIn] = Field(default_factory=list)


class ProductCreate(BaseModel):
    store_id: int
    name: str
    category: str = ""
    price_min: float | None = None
    price_max: float | None = None
    description: str = ""
    main_sku_id: int | None = None
    skus: list[SkuIn] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    store_id: int | None = None
    name: str | None = None
    category: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    description: str | None = None
    main_sku_id: int | None = None


def parse_spec_text(text: str | None) -> dict[str, str]:
    """把「颜色:雾霾蓝, 尺码:M」解析为结构化规格。"""
    text = (text or "").strip()
    if not text:
        return {"规格": "标准"}
    result: dict[str, str] = {}
    for part in text.replace("；", ";").replace("，", ",").replace("、", ",").split(";"):
        for chunk in part.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            separator = ":" if ":" in chunk else ("：" if "：" in chunk else None)
            if separator:
                key, value = chunk.split(separator, 1)
                key, value = key.strip(), value.strip()
            else:
                key, value = "规格", chunk
            if key and value:
                result[key] = value
    return result or {"规格": "标准"}


def sku_view(
    sku: Sku,
    mappings: list[PlatformSkuMapping] | None = None,
    is_service: bool = False,
) -> dict:
    return {
        "id": sku.id,
        "spec": sku.spec_json,
        "price": sku.price,
        "stock": sku.stock,
        "warn_threshold": sku.warn_threshold,
        "warning": False if is_service else sku.stock <= sku.warn_threshold,
        "mappings": [
            mapping_view(mapping)
            for mapping in (mappings if mappings is not None else sku.mappings)
        ],
    }


def mapping_view(mapping: PlatformSkuMapping) -> dict:
    return {
        "id": mapping.id,
        "sku_id": mapping.sku_id,
        "platform": mapping.platform,
        "platform_spec_name": mapping.platform_spec_name,
        "platform_price": mapping.platform_price,
        "platform_sku_code": mapping.platform_sku_code,
    }


def product_detail(db, product: Product) -> dict:
    store = db.get(Store, product.store_id)
    skus = db.scalars(
        select(Sku)
        .options(selectinload(Sku.mappings))
        .where(Sku.product_id == product.id)
        .order_by(Sku.id)
    ).all()
    stage = product_stage(db, product.id)
    is_service = is_service_category(product.category)
    return {
        "id": product.id,
        "name": product.name,
        "category": product.category,
        "is_service": is_service,
        "price_unit": price_unit_for(product.category),
        "price_min": product.price_min,
        "price_max": product.price_max,
        "description": product.description,
        "store": {"id": store.id, "name": store.name, "platform": store.platform},
        "main_sku_id": product.main_sku_id,
        "skus": [sku_view(sku, list(sku.mappings), is_service=is_service) for sku in skus],
        "archived": product.archived,
        "stage": stage,
        "stage_label": STAGE_LABELS[stage],
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
    }


def _validate_price_band(price_min: float, price_max: float) -> None:
    if price_min < 0 or price_max < 0:
        raise HTTPException(status_code=400, detail="价格不能为负数")
    if price_min > price_max:
        raise HTTPException(status_code=400, detail="价格带下限不能高于上限")


def _validate_platform(platform: str) -> str:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台：{platform}")
    return platform


@router.get("")
def list_products(
    db: DbSession,
    _: CurrentUser,
    store_id: int | None = None,
    keyword: str | None = None,
    stage: str | None = None,
    include_archived: bool = False,
):
    stmt = select(Product).options(selectinload(Product.skus), selectinload(Product.store))
    if not include_archived:
        stmt = stmt.where(Product.archived.is_(False))
    if store_id:
        stmt = stmt.where(Product.store_id == store_id)
    if keyword:
        stmt = stmt.where(Product.name.contains(keyword))
    products = db.scalars(stmt.order_by(Product.updated_at.desc())).all()

    result = []
    for product in products:
        if product.archived and not include_archived:
            continue
        product_stage_value = product_stage(db, product.id)
        if stage and product_stage_value != stage:
            continue
        is_service = is_service_category(product.category)
        warning_skus = [] if is_service else [
            s for s in product.skus if s.stock <= s.warn_threshold
        ]
        main_sku = next((s for s in product.skus if s.id == product.main_sku_id), None)
        asset_count = db.scalar(
            select(func.count(Asset.id)).where(Asset.product_id == product.id)
        ) or 0
        result.append(
            {
                "id": product.id,
                "name": product.name,
                "category": product.category,
                "is_service": is_service,
                "price_unit": price_unit_for(product.category),
                "price_min": product.price_min,
                "price_max": product.price_max,
                "description": product.description,
                "store": {
                    "id": product.store.id,
                    "name": product.store.name,
                    "platform": product.store.platform,
                },
                "sku_count": len(product.skus),
                "main_sku_spec": main_sku.spec_json if main_sku else None,
                "warning_sku_count": len(warning_skus),
                "asset_count": asset_count,
                "archived": product.archived,
                "stage": product_stage_value,
                "stage_label": STAGE_LABELS[product_stage_value],
                "updated_at": product.updated_at.isoformat(),
            }
        )
    return result


@router.post("", status_code=201)
def create_product(payload: ProductCreate, db: DbSession, _: CurrentUser):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="商品名称不能为空")

    store = db.get(Store, payload.store_id)
    if store is None:
        raise HTTPException(status_code=400, detail="所属店铺不存在")

    is_service = is_service_category(payload.category)
    prices = [float(item.price) for item in payload.skus if item.price and item.price > 0]
    price_min = payload.price_min if payload.price_min is not None else (min(prices) if prices else 0)
    price_max = payload.price_max if payload.price_max is not None else (max(prices) if prices else price_min)
    _validate_price_band(float(price_min), float(price_max))

    for item in payload.skus:
        if item.price < 0:
            raise HTTPException(status_code=400, detail="SKU 售价不能为负数")
        if item.stock < 0:
            raise HTTPException(status_code=400, detail="SKU 库存不能为负数")
        if item.warn_threshold < 0:
            raise HTTPException(status_code=400, detail="安全库存不能为负数")
        for mapping in item.mappings:
            _validate_platform(mapping.platform or store.platform)

    product = Product(
        store_id=payload.store_id,
        name=name,
        category=payload.category.strip(),
        price_min=float(price_min),
        price_max=float(price_max),
        description=payload.description.strip(),
        main_sku_id=None,
    )
    db.add(product)
    db.flush()

    created_skus: list[Sku] = []
    for item in payload.skus:
        spec = item.spec_json or parse_spec_text(item.spec_text)
        sku = Sku(
            product_id=product.id,
            spec_json=spec,
            price=float(item.price),
            stock=SERVICE_SKU_STOCK if is_service else int(item.stock),
            warn_threshold=SERVICE_SKU_WARN_THRESHOLD if is_service else int(item.warn_threshold),
        )
        db.add(sku)
        db.flush()
        created_skus.append(sku)
        for mapping in item.mappings:
            platform = _validate_platform(mapping.platform or store.platform)
            db.add(
                PlatformSkuMapping(
                    sku_id=sku.id,
                    platform=platform,
                    platform_spec_name=mapping.platform_spec_name
                    or " / ".join(str(v) for v in spec.values()),
                    platform_price=float(
                        mapping.platform_price if mapping.platform_price is not None else item.price
                    ),
                    platform_sku_code=mapping.platform_sku_code,
                )
            )

    if payload.main_sku_id is not None:
        if payload.main_sku_id not in {sku.id for sku in created_skus}:
            raise HTTPException(status_code=400, detail="主推 SKU 必须属于该商品")
        product.main_sku_id = payload.main_sku_id
    elif created_skus:
        product.main_sku_id = created_skus[0].id

    db.commit()
    db.refresh(product)
    return product_detail(db, product)


@router.post("/{product_id}/archive")
def archive_product(
    product_id: int,
    db: DbSession,
    _: CurrentUser,
    archived: bool = True,
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    product.archived = archived
    db.commit()
    db.refresh(product)
    return {
        "id": product.id,
        "archived": product.archived,
        "message": "商品已归档" if product.archived else "商品已恢复",
    }


@router.get("/{product_id}")
def get_product(product_id: int, db: DbSession, _: CurrentUser):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product_detail(db, product)


@router.put("/{product_id}")
def update_product(product_id: int, payload: ProductUpdate, db: DbSession, _: CurrentUser):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    if payload.store_id is not None:
        if db.get(Store, payload.store_id) is None:
            raise HTTPException(status_code=400, detail="所属店铺不存在")
        product.store_id = payload.store_id
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="商品名称不能为空")
        product.name = name
    if payload.category is not None:
        product.category = payload.category.strip()
    if payload.description is not None:
        product.description = payload.description.strip()

    next_min = float(payload.price_min) if payload.price_min is not None else float(product.price_min)
    next_max = float(payload.price_max) if payload.price_max is not None else float(product.price_max)
    _validate_price_band(next_min, next_max)
    product.price_min = next_min
    product.price_max = next_max

    if payload.main_sku_id is not None:
        sku_ids = set(
            db.scalars(select(Sku.id).where(Sku.product_id == product.id)).all()
        )
        if payload.main_sku_id not in sku_ids:
            raise HTTPException(status_code=400, detail="主推 SKU 必须属于该商品")
        product.main_sku_id = payload.main_sku_id

    db.commit()
    db.refresh(product)
    return product_detail(db, product)


@router.get("/{product_id}/metric-trend")
def metric_trend(product_id: int, db: DbSession, _: CurrentUser, days: int = 14):
    """单品经营指标走势（供工作台复盘区使用）。"""
    from ..models import MetricRecord

    start = date.today() - timedelta(days=days - 1)
    rows = db.execute(
        select(
            MetricRecord.date,
            func.sum(MetricRecord.impressions),
            func.sum(MetricRecord.clicks),
            func.sum(MetricRecord.orders),
            func.sum(MetricRecord.gmv),
            func.sum(MetricRecord.spend),
        )
        .where(MetricRecord.product_id == product_id, MetricRecord.date >= start.isoformat())
        .group_by(MetricRecord.date)
        .order_by(MetricRecord.date)
    ).all()
    return [
        {
            "date": r[0],
            "impressions": int(r[1] or 0),
            "clicks": int(r[2] or 0),
            "orders": int(r[3] or 0),
            "gmv": round(float(r[4] or 0), 2),
            "spend": round(float(r[5] or 0), 2),
            "ctr": round((r[2] or 0) / (r[1] or 1), 4),
            "cvr": round((r[3] or 0) / (r[2] or 1), 4),
            "roi": round((r[4] or 0) / (r[5] or 1), 2),
        }
        for r in rows
    ]
