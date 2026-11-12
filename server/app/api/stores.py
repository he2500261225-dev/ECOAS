from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ..models import Product, Sku, Store, User
from ..security import CurrentUser, DbSession, require_roles
from ..services.service_profiles import SERVICE_CATEGORIES

router = APIRouter(prefix="/api/stores", tags=["stores"])

PLATFORMS = {"taobao", "jd", "douyin", "pdd", "local"}
AUTH_STATUSES = {"authorized", "expired", "pending", "revoked"}


class StoreCreate(BaseModel):
    name: str
    platform: str
    auth_status: str = "authorized"
    auth_ref: str = ""


class StoreUpdate(BaseModel):
    name: str | None = None
    platform: str | None = None
    auth_status: str | None = None
    auth_ref: str | None = None


def mask_auth_ref(value: str | None) -> str:
    """授权标识只保留脱敏形态，避免把明文凭据写入数据库。"""
    value = (value or "").strip()
    if not value:
        return ""
    if "*" in value:
        return value
    if len(value) <= 4:
        return "****"
    prefix = value[:6] if len(value) > 10 else value[:2]
    return f"{prefix}****{value[-4:]}"


def _validate_platform(platform: str) -> str:
    if platform not in PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台：{platform}")
    return platform


def _validate_auth_status(auth_status: str) -> str:
    if auth_status not in AUTH_STATUSES:
        raise HTTPException(status_code=400, detail=f"不支持的授权状态：{auth_status}")
    return auth_status


def _store_view(db, store: Store) -> dict:
    product_count = db.scalar(
        select(func.count(Product.id)).where(Product.store_id == store.id)
    ) or 0
    warning_count = db.scalar(
        select(func.count(Sku.id))
        .join(Product, Product.id == Sku.product_id)
        .where(
            Product.store_id == store.id,
            Product.category.notin_(SERVICE_CATEGORIES),
            Sku.stock <= Sku.warn_threshold,
        )
    ) or 0
    return {
        "id": store.id,
        "name": store.name,
        "platform": store.platform,
        "auth_status": store.auth_status,
        "auth_ref": store.auth_ref,
        "product_count": product_count,
        "stock_warning_count": warning_count,
    }


@router.get("")
def list_stores(db: DbSession, _: CurrentUser):
    stores = db.scalars(select(Store).order_by(Store.id)).all()
    return [_store_view(db, store) for store in stores]


@router.post("", status_code=201)
def create_store(
    payload: StoreCreate,
    db: DbSession,
    _: User = Depends(require_roles("manager")),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="店铺名称不能为空")
    _validate_platform(payload.platform)
    _validate_auth_status(payload.auth_status)
    store = Store(
        name=name,
        platform=payload.platform,
        auth_status=payload.auth_status,
        auth_ref=mask_auth_ref(payload.auth_ref),
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return _store_view(db, store)


@router.put("/{store_id}")
def update_store(
    store_id: int,
    payload: StoreUpdate,
    db: DbSession,
    _: User = Depends(require_roles("manager")),
):
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="店铺不存在")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="店铺名称不能为空")
        store.name = name
    if payload.platform is not None:
        store.platform = _validate_platform(payload.platform)
    if payload.auth_status is not None:
        store.auth_status = _validate_auth_status(payload.auth_status)
    if payload.auth_ref is not None:
        store.auth_ref = mask_auth_ref(payload.auth_ref)

    db.commit()
    db.refresh(store)
    return _store_view(db, store)
