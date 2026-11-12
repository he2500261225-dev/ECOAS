from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Asset, Product, User, utcnow
from ..security import CurrentUser, DbSession

router = APIRouter(prefix="/api", tags=["assets"])

ASSET_TYPES = {"image", "video"}
ASSET_STATUSES = {"pending_review", "approved", "rejected", "archived"}


class AssetReviewIn(BaseModel):
    action: str  # approve | reject
    note: str = ""


class AssetTagsIn(BaseModel):
    tags: list[str] = []


def asset_view(db: Session, asset: Asset) -> dict:
    reviewer = db.get(User, asset.reviewed_by) if asset.reviewed_by else None
    return {
        "id": asset.id,
        "product_id": asset.product_id,
        "task_id": asset.task_id,
        "type": asset.type,
        "source_type": asset.source_type,
        "source_id": asset.source_id,
        "filename": asset.filename,
        "file_path": asset.file_path,
        "mime": asset.mime,
        "version": asset.version,
        "status": asset.status,
        "tags_json": asset.tags_json or [],
        "review_note": asset.review_note,
        "reviewed_by": asset.reviewed_by,
        "reviewed_by_name": reviewer.display_name if reviewer else "",
        "reviewed_at": asset.reviewed_at.isoformat() if asset.reviewed_at else None,
        "created_at": asset.created_at.isoformat(),
    }


@router.get("/products/{product_id}/assets")
def list_assets(
    product_id: int,
    db: DbSession,
    _: CurrentUser,
    type: str | None = None,
    status: str | None = None,
):
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    if type and type not in ASSET_TYPES:
        raise HTTPException(status_code=400, detail="type 仅支持 image / video")
    if status and status not in ASSET_STATUSES:
        raise HTTPException(status_code=400, detail="不支持的素材状态")

    stmt = select(Asset).where(Asset.product_id == product_id)
    if type:
        stmt = stmt.where(Asset.type == type)
    if status:
        stmt = stmt.where(Asset.status == status)
    rows = db.scalars(stmt.order_by(Asset.created_at.desc(), Asset.id.desc())).all()
    return [asset_view(db, item) for item in rows]


def _asset_or_404(db: Session, asset_id: int) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    return asset


@router.post("/assets/{asset_id}/review")
def review_asset(
    asset_id: int, payload: AssetReviewIn, db: DbSession, user: CurrentUser
):
    asset = _asset_or_404(db, asset_id)
    if asset.status != "pending_review":
        raise HTTPException(status_code=400, detail="仅待审核素材可执行审核操作")

    action = payload.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action 仅支持 approve / reject")
    note = payload.note.strip()
    if action == "reject" and not note:
        raise HTTPException(status_code=400, detail="驳回素材必须填写审核备注")

    asset.status = "approved" if action == "approve" else "rejected"
    asset.review_note = note
    asset.reviewed_by = user.id
    asset.reviewed_at = utcnow()
    db.commit()
    db.refresh(asset)
    return asset_view(db, asset)


@router.put("/assets/{asset_id}/tags")
def update_asset_tags(asset_id: int, payload: AssetTagsIn, db: DbSession, _: CurrentUser):
    asset = _asset_or_404(db, asset_id)
    tags: list[str] = []
    for item in payload.tags:
        tag = str(item).strip()
        if tag and tag not in tags:
            tags.append(tag[:20])
    if len(tags) > 10:
        raise HTTPException(status_code=400, detail="单个素材最多 10 个标签")
    asset.tags_json = tags
    db.commit()
    db.refresh(asset)
    return asset_view(db, asset)


@router.post("/assets/{asset_id}/archive")
def archive_asset(asset_id: int, db: DbSession, _: CurrentUser):
    asset = _asset_or_404(db, asset_id)
    if asset.status == "archived":
        return asset_view(db, asset)
    if asset.status != "approved":
        raise HTTPException(status_code=400, detail="仅审核通过的素材可归档")
    asset.status = "archived"
    db.commit()
    db.refresh(asset)
    return asset_view(db, asset)
