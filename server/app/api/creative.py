from __future__ import annotations

import copy

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import CreativePlan, Diagnosis, ImageScheme, Product, VideoScript, VideoShot
from ..security import CurrentUser, DbSession
from ..services import llm
from ..services.service_profiles import service_context

router = APIRouter(prefix="/api", tags=["creative"])

MIN_IMAGE_SCHEMES = 3
MIN_VIDEO_SCRIPTS = 3
MIN_SHOTS = 4


class GenerateCreativeIn(BaseModel):
    diagnosis_id: int | None = None


class ImageSchemeUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    layout: str | None = None
    copy_text: str | None = Field(default=None, alias="copy")
    main_selling_point: str | None = None
    visual_tip: str | None = None
    order_no: int | None = None


class VideoScriptUpdate(BaseModel):
    title: str | None = None
    hook_3s: str | None = None
    closing_cta: str | None = None
    order_no: int | None = None


class VideoShotCreate(BaseModel):
    duration_sec: int = Field(default=3, ge=1, le=60)
    scene_desc: str
    voiceover: str = ""
    cta_line: str = ""


class VideoShotUpdate(BaseModel):
    duration_sec: int | None = Field(default=None, ge=1, le=60)
    scene_desc: str | None = None
    voiceover: str | None = None
    cta_line: str | None = None


# ---------------------------------------------------------------------------
# 视图
# ---------------------------------------------------------------------------


def shot_view(shot: VideoShot) -> dict:
    return {
        "id": shot.id,
        "script_id": shot.script_id,
        "shot_no": shot.shot_no,
        "duration_sec": shot.duration_sec,
        "scene_desc": shot.scene_desc,
        "voiceover": shot.voiceover,
        "cta_line": shot.cta_line,
    }


def script_view(script: VideoScript) -> dict:
    return {
        "id": script.id,
        "plan_id": script.plan_id,
        "order_no": script.order_no,
        "title": script.title,
        "hook_3s": script.hook_3s,
        "closing_cta": script.closing_cta,
        "status": script.status,
        "shots": [shot_view(item) for item in script.shots],
        "total_duration": sum(int(item.duration_sec or 0) for item in script.shots),
    }


def scheme_view(scheme: ImageScheme) -> dict:
    return {
        "id": scheme.id,
        "plan_id": scheme.plan_id,
        "order_no": scheme.order_no,
        "title": scheme.title,
        "layout": scheme.layout,
        "copy": scheme.copy,
        "main_selling_point": scheme.main_selling_point,
        "visual_tip": scheme.visual_tip,
        "status": scheme.status,
    }


def plan_view(plan: CreativePlan) -> dict:
    return {
        "id": plan.id,
        "product_id": plan.product_id,
        "diagnosis_id": plan.diagnosis_id,
        "version": plan.version,
        "status": plan.status,
        "created_at": plan.created_at.isoformat(),
        "image_schemes": [scheme_view(item) for item in plan.image_schemes],
        "video_scripts": [script_view(item) for item in plan.video_scripts],
    }


def _load_plan(db: Session, plan_id: int) -> CreativePlan:
    plan = db.scalar(
        select(CreativePlan)
        .options(
            selectinload(CreativePlan.image_schemes),
            selectinload(CreativePlan.video_scripts).selectinload(VideoScript.shots),
        )
        .where(CreativePlan.id == plan_id)
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="创意方案不存在")
    return plan


def _recompute_plan_status(db: Session, plan_id: int) -> None:
    plan = _load_plan(db, plan_id)
    items = list(plan.image_schemes) + list(plan.video_scripts)
    active = [item for item in items if item.status != "archived"]
    if not items:
        plan.status = "draft"
    elif not active:
        plan.status = "archived"
    elif all(item.status == "confirmed" for item in active):
        plan.status = "confirmed"
    else:
        plan.status = "draft"
    db.commit()


# ---------------------------------------------------------------------------
# 生成与查询
# ---------------------------------------------------------------------------


def _creative_context(db: Session, product: Product, diagnosis: Diagnosis) -> dict:
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
        "diagnosis_version": diagnosis.version,
        "diagnosis": diagnosis.content_json or {},
    }


def _ensure_minimums(content: dict, context: dict) -> tuple[dict, list[str]]:
    """强制满足演示下限：≥3 组主图、≥3 套脚本、每套 ≥4 个分镜。"""
    warnings: list[str] = []
    data = {
        "image_schemes": [
            copy.deepcopy(item)
            for item in (content.get("image_schemes") or [])
            if isinstance(item, dict)
        ],
        "video_scripts": [
            copy.deepcopy(item)
            for item in (content.get("video_scripts") or [])
            if isinstance(item, dict)
        ],
    }
    mock = llm.mock_content("creative_plan", context)
    mock_schemes = mock.get("image_schemes") or []
    mock_scripts = mock.get("video_scripts") or []

    if len(data["image_schemes"]) < MIN_IMAGE_SCHEMES:
        need = MIN_IMAGE_SCHEMES - len(data["image_schemes"])
        for item in copy.deepcopy(mock_schemes[:need]):
            item["title"] = f"{item.get('title') or '补充方案'}（自动补足）"
            data["image_schemes"].append(item)
        warnings.append(f"主图方案不足 {MIN_IMAGE_SCHEMES} 组，已自动补足至下限。")

    if len(data["video_scripts"]) < MIN_VIDEO_SCRIPTS:
        need = MIN_VIDEO_SCRIPTS - len(data["video_scripts"])
        for item in copy.deepcopy(mock_scripts[:need]):
            item["title"] = f"{item.get('title') or '补充脚本'}（自动补足）"
            data["video_scripts"].append(item)
        warnings.append(f"视频脚本不足 {MIN_VIDEO_SCRIPTS} 套，已自动补足至下限。")

    for index, script in enumerate(data["video_scripts"]):
        shots = [item for item in (script.get("shots") or []) if isinstance(item, dict)]
        if len(shots) >= MIN_SHOTS:
            script["shots"] = shots
            continue
        filler = mock_scripts[min(index, len(mock_scripts) - 1)]["shots"] if mock_scripts else []
        for item in copy.deepcopy(filler[len(shots) : MIN_SHOTS]):
            shots.append(item)
        script["shots"] = shots
        warnings.append(
            f"「{script.get('title') or f'脚本 {index + 1}'}」分镜不足 {MIN_SHOTS} 个，已自动补足。"
        )

    try:
        validated = llm.validate_content("creative_plan", data)
    except Exception as exc:  # 真实输出结构异常时整体回退 Mock，保证演示可用
        fallback = llm.mock_content("creative_plan", context)
        warnings.append(f"创意内容结构校验失败，已回退 Mock：{exc}")
        return fallback, warnings
    return validated, warnings


@router.post("/products/{product_id}/creative-plans/generate")
def generate_creative_plan(
    product_id: int,
    payload: GenerateCreativeIn,
    db: DbSession,
    user: CurrentUser,
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="商品不存在")

    if payload.diagnosis_id is not None:
        diagnosis = db.get(Diagnosis, payload.diagnosis_id)
        if diagnosis is None:
            raise HTTPException(status_code=404, detail="诊断不存在")
        if diagnosis.product_id != product.id:
            raise HTTPException(status_code=400, detail="诊断不属于该商品")
    else:
        diagnosis = db.scalar(
            select(Diagnosis).where(
                Diagnosis.product_id == product.id, Diagnosis.status == "current"
            )
        )
    if diagnosis is None:
        raise HTTPException(status_code=400, detail="请先生成当前版本诊断，再生成创意方案")

    context = _creative_context(db, product, diagnosis)
    result = llm.generate_structured(db, "creative_plan", context)
    content, pad_warnings = _ensure_minimums(result.content, context)
    warnings = list(result.warnings) + pad_warnings

    next_version = (
        db.scalar(
            select(func.max(CreativePlan.version)).where(
                CreativePlan.product_id == product.id
            )
        )
        or 0
    ) + 1

    plan = CreativePlan(
        product_id=product.id,
        diagnosis_id=diagnosis.id,
        version=next_version,
        status="draft",
    )
    db.add(plan)
    db.flush()

    for index, scheme in enumerate(content["image_schemes"], start=1):
        db.add(
            ImageScheme(
                plan_id=plan.id,
                order_no=index,
                title=scheme["title"],
                layout=scheme["layout"],
                copy=scheme["copy"],
                main_selling_point=scheme["main_selling_point"],
                visual_tip=scheme["visual_tip"],
                status="draft",
            )
        )

    for index, script in enumerate(content["video_scripts"], start=1):
        row = VideoScript(
            plan_id=plan.id,
            order_no=index,
            title=script["title"],
            hook_3s=script["hook_3s"],
            closing_cta=script["closing_cta"],
            status="draft",
        )
        db.add(row)
        db.flush()
        for shot_no, shot in enumerate(script["shots"], start=1):
            db.add(
                VideoShot(
                    script_id=row.id,
                    shot_no=shot_no,
                    duration_sec=int(shot["duration_sec"]),
                    scene_desc=shot["scene_desc"],
                    voiceover=shot.get("voiceover", ""),
                    cta_line=shot.get("cta_line", ""),
                )
            )

    db.commit()
    plan = _load_plan(db, plan.id)

    data = plan_view(plan)
    data["generate_channel"] = result.channel
    data["model"] = result.model
    data["note"] = result.note
    data["warnings"] = warnings
    return data


@router.get("/products/{product_id}/creative-plans")
def list_creative_plans(product_id: int, db: DbSession, _: CurrentUser):
    if db.get(Product, product_id) is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    plans = db.scalars(
        select(CreativePlan)
        .options(
            selectinload(CreativePlan.image_schemes),
            selectinload(CreativePlan.video_scripts).selectinload(VideoScript.shots),
        )
        .where(CreativePlan.product_id == product_id)
        .order_by(CreativePlan.version.desc())
    ).all()
    return [plan_view(item) for item in plans]


@router.get("/creative-plans/{plan_id}")
def get_creative_plan(plan_id: int, db: DbSession, _: CurrentUser):
    return plan_view(_load_plan(db, plan_id))


# ---------------------------------------------------------------------------
# 主图方案编辑
# ---------------------------------------------------------------------------


def _scheme_or_404(db: Session, scheme_id: int) -> ImageScheme:
    scheme = db.get(ImageScheme, scheme_id)
    if scheme is None:
        raise HTTPException(status_code=404, detail="主图方案不存在")
    return scheme


@router.put("/image-schemes/{scheme_id}")
def update_image_scheme(
    scheme_id: int, payload: ImageSchemeUpdate, db: DbSession, _: CurrentUser
):
    scheme = _scheme_or_404(db, scheme_id)
    if scheme.status == "archived":
        raise HTTPException(status_code=400, detail="已归档方案不可编辑")

    for field in ("layout", "main_selling_point", "visual_tip"):
        value = getattr(payload, field)
        if value is not None:
            setattr(scheme, field, value.strip())
    if payload.copy_text is not None:
        scheme.copy = payload.copy_text.strip()
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="方案标题不能为空")
        scheme.title = title
    if payload.order_no is not None:
        if payload.order_no < 1:
            raise HTTPException(status_code=400, detail="排序号必须大于 0")
        scheme.order_no = payload.order_no

    if scheme.status == "confirmed":
        scheme.status = "draft"  # 内容变更后需要重新确认
    db.commit()
    _recompute_plan_status(db, scheme.plan_id)
    return scheme_view(_scheme_or_404(db, scheme_id))


@router.post("/image-schemes/{scheme_id}/confirm")
def confirm_image_scheme(scheme_id: int, db: DbSession, _: CurrentUser):
    scheme = _scheme_or_404(db, scheme_id)
    if scheme.status == "archived":
        raise HTTPException(status_code=400, detail="已归档方案不可确认")
    scheme.status = "confirmed"
    db.commit()
    _recompute_plan_status(db, scheme.plan_id)
    return scheme_view(_scheme_or_404(db, scheme_id))


@router.post("/image-schemes/{scheme_id}/archive")
def archive_image_scheme(scheme_id: int, db: DbSession, _: CurrentUser):
    scheme = _scheme_or_404(db, scheme_id)
    scheme.status = "archived"
    db.commit()
    _recompute_plan_status(db, scheme.plan_id)
    return scheme_view(_scheme_or_404(db, scheme_id))


# ---------------------------------------------------------------------------
# 视频脚本与分镜编辑
# ---------------------------------------------------------------------------


def _script_or_404(db: Session, script_id: int) -> VideoScript:
    script = db.scalar(
        select(VideoScript)
        .options(selectinload(VideoScript.shots))
        .where(VideoScript.id == script_id)
    )
    if script is None:
        raise HTTPException(status_code=404, detail="视频脚本不存在")
    return script


def _shot_or_404(db: Session, shot_id: int) -> VideoShot:
    shot = db.get(VideoShot, shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return shot


def _touch_script(db: Session, script: VideoScript) -> None:
    if script.status == "confirmed":
        script.status = "draft"


@router.put("/video-scripts/{script_id}")
def update_video_script(
    script_id: int, payload: VideoScriptUpdate, db: DbSession, _: CurrentUser
):
    script = _script_or_404(db, script_id)
    if script.status == "archived":
        raise HTTPException(status_code=400, detail="已归档脚本不可编辑")

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="脚本标题不能为空")
        script.title = title
    if payload.hook_3s is not None:
        script.hook_3s = payload.hook_3s.strip()
    if payload.closing_cta is not None:
        script.closing_cta = payload.closing_cta.strip()
    if payload.order_no is not None:
        if payload.order_no < 1:
            raise HTTPException(status_code=400, detail="排序号必须大于 0")
        script.order_no = payload.order_no

    _touch_script(db, script)
    db.commit()
    _recompute_plan_status(db, script.plan_id)
    return script_view(_script_or_404(db, script_id))


@router.post("/video-scripts/{script_id}/confirm")
def confirm_video_script(script_id: int, db: DbSession, _: CurrentUser):
    script = _script_or_404(db, script_id)
    if script.status == "archived":
        raise HTTPException(status_code=400, detail="已归档脚本不可确认")
    if len(script.shots) < MIN_SHOTS:
        raise HTTPException(status_code=400, detail=f"分镜少于 {MIN_SHOTS} 个，请先补充分镜")
    script.status = "confirmed"
    db.commit()
    _recompute_plan_status(db, script.plan_id)
    return script_view(_script_or_404(db, script_id))


@router.post("/video-scripts/{script_id}/archive")
def archive_video_script(script_id: int, db: DbSession, _: CurrentUser):
    script = _script_or_404(db, script_id)
    script.status = "archived"
    db.commit()
    _recompute_plan_status(db, script.plan_id)
    return script_view(_script_or_404(db, script_id))


@router.post("/video-scripts/{script_id}/shots", status_code=201)
def create_video_shot(
    script_id: int, payload: VideoShotCreate, db: DbSession, _: CurrentUser
):
    script = _script_or_404(db, script_id)
    if script.status == "archived":
        raise HTTPException(status_code=400, detail="已归档脚本不可编辑")
    next_no = max([item.shot_no for item in script.shots] or [0]) + 1
    shot = VideoShot(
        script_id=script.id,
        shot_no=next_no,
        duration_sec=int(payload.duration_sec),
        scene_desc=payload.scene_desc.strip(),
        voiceover=payload.voiceover.strip(),
        cta_line=payload.cta_line.strip(),
    )
    db.add(shot)
    _touch_script(db, script)
    db.commit()
    db.refresh(shot)
    _recompute_plan_status(db, script.plan_id)
    return shot_view(shot)


@router.put("/video-shots/{shot_id}")
def update_video_shot(
    shot_id: int, payload: VideoShotUpdate, db: DbSession, _: CurrentUser
):
    shot = _shot_or_404(db, shot_id)
    script = _script_or_404(db, shot.script_id)
    if script.status == "archived":
        raise HTTPException(status_code=400, detail="已归档脚本不可编辑")

    if payload.duration_sec is not None:
        shot.duration_sec = int(payload.duration_sec)
    for field in ("scene_desc", "voiceover", "cta_line"):
        value = getattr(payload, field)
        if value is not None:
            setattr(shot, field, value.strip())

    _touch_script(db, script)
    db.commit()
    db.refresh(shot)
    _recompute_plan_status(db, script.plan_id)
    return shot_view(shot)


@router.delete("/video-shots/{shot_id}")
def delete_video_shot(shot_id: int, db: DbSession, _: CurrentUser):
    shot = _shot_or_404(db, shot_id)
    script = _script_or_404(db, shot.script_id)
    if script.status == "archived":
        raise HTTPException(status_code=400, detail="已归档脚本不可编辑")
    if len(script.shots) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个分镜")

    db.delete(shot)
    db.flush()
    remaining = db.scalars(
        select(VideoShot)
        .where(VideoShot.script_id == script.id)
        .order_by(VideoShot.shot_no, VideoShot.id)
    ).all()
    for index, item in enumerate(remaining, start=1):
        item.shot_no = index
    _touch_script(db, script)
    db.commit()
    _recompute_plan_status(db, script.plan_id)
    return {"ok": True, "message": "分镜已删除"}
