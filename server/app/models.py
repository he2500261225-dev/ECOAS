from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), default="operator")  # operator | manager
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(20))  # taobao | jd | douyin | pdd
    auth_status: Mapped[str] = mapped_column(String(20), default="authorized")
    auth_ref: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    products: Mapped[list["Product"]] = relationship(back_populates="store")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    price_min: Mapped[float] = mapped_column(Float, default=0)
    price_max: Mapped[float] = mapped_column(Float, default=0)
    main_sku_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    store: Mapped[Store] = relationship(back_populates="products")
    skus: Mapped[list["Sku"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    competitors: Mapped[list["Competitor"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Sku(Base):
    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    spec_json: Mapped[dict] = mapped_column(JSON, default=dict)
    price: Mapped[float] = mapped_column(Float, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    warn_threshold: Mapped[int] = mapped_column(Integer, default=10)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product: Mapped[Product] = relationship(back_populates="skus")
    mappings: Mapped[list["PlatformSkuMapping"]] = relationship(
        back_populates="sku", cascade="all, delete-orphan"
    )


class PlatformSkuMapping(Base):
    __tablename__ = "platform_sku_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    platform: Mapped[str] = mapped_column(String(20))
    platform_spec_name: Mapped[str] = mapped_column(String(200))
    platform_price: Mapped[float] = mapped_column(Float, default=0)
    platform_sku_code: Mapped[str] = mapped_column(String(100), default="")

    sku: Mapped[Sku] = relationship(back_populates="mappings")


class StockFlow(Base):
    __tablename__ = "stock_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id"))
    change: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(50), default="manual")
    stock_after: Mapped[int] = mapped_column(Integer, default=0)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    platform: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[float] = mapped_column(Float, default=0)
    url: Mapped[str] = mapped_column(String(500), default="")
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    sales_volume: Mapped[int] = mapped_column(Integer, default=0)
    rating: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ai_parse
    parse_status: Mapped[str] = mapped_column(String(20), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    product: Mapped[Product] = relationship(back_populates="competitors")


class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="current")  # current | history
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_report_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str] = mapped_column(String(100), default="mock")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CreativePlan(Base):
    __tablename__ = "creative_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    diagnosis_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | confirmed | archived
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    image_schemes: Mapped[list["ImageScheme"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="ImageScheme.order_no"
    )
    video_scripts: Mapped[list["VideoScript"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="VideoScript.order_no"
    )


class ImageScheme(Base):
    __tablename__ = "image_schemes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("creative_plans.id"))
    order_no: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200))
    layout: Mapped[str] = mapped_column(Text, default="")
    copy: Mapped[str] = mapped_column(Text, default="")
    main_selling_point: Mapped[str] = mapped_column(Text, default="")
    visual_tip: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | confirmed | archived

    plan: Mapped[CreativePlan] = relationship(back_populates="image_schemes")


class VideoScript(Base):
    __tablename__ = "video_scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("creative_plans.id"))
    order_no: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200))
    hook_3s: Mapped[str] = mapped_column(Text, default="")
    closing_cta: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")

    plan: Mapped[CreativePlan] = relationship(back_populates="video_scripts")
    shots: Mapped[list["VideoShot"]] = relationship(
        back_populates="script", cascade="all, delete-orphan", order_by="VideoShot.shot_no"
    )


class VideoShot(Base):
    __tablename__ = "video_shots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("video_scripts.id"))
    shot_no: Mapped[int] = mapped_column(Integer, default=1)
    duration_sec: Mapped[int] = mapped_column(Integer, default=3)
    scene_desc: Mapped[str] = mapped_column(Text, default="")
    voiceover: Mapped[str] = mapped_column(Text, default="")
    cta_line: Mapped[str] = mapped_column(Text, default="")

    script: Mapped[VideoScript] = relationship(back_populates="shots")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String(20))  # image | video
    source_type: Mapped[str] = mapped_column(String(30), default="image_scheme")
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100), default="image/svg+xml")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending_review")
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    type: Mapped[str] = mapped_column(String(20))  # image | video
    source_type: Mapped[str] = mapped_column(String(30))  # image_scheme | video_script
    source_id: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_retry: Mapped[int] = mapped_column(Integer, default=2)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300)
    worker_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    result_asset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TaskAttempt(Base):
    __tablename__ = "task_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("generation_tasks.id"))
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    error_message: Mapped[str] = mapped_column(Text, default="")


class Placement(Base):
    __tablename__ = "placements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    creative_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audience_json: Mapped[dict] = mapped_column(JSON, default=dict)
    bid_json: Mapped[dict] = mapped_column(JSON, default=dict)
    budget: Mapped[float] = mapped_column(Float, default=0)
    period_start: Mapped[str] = mapped_column(String(10), default="")
    period_end: Mapped[str] = mapped_column(String(10), default="")
    ab_json: Mapped[list] = mapped_column(JSON, default=list)
    risk_level: Mapped[str] = mapped_column(String(10), default="low")  # low | high
    status: Mapped[str] = mapped_column(String(30), default="draft")
    targets_json: Mapped[dict] = mapped_column(JSON, default=dict)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ApprovalLog(Base):
    __tablename__ = "approval_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    placement_id: Mapped[int] = mapped_column(ForeignKey("placements.id"))
    action: Mapped[str] = mapped_column(String(20))  # submit | approve | reject
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_name: Mapped[str] = mapped_column(String(50), default="")
    role: Mapped[str] = mapped_column(String(20), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MetricRecord(Base):
    __tablename__ = "metric_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    placement_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    gmv: Mapped[float] = mapped_column(Float, default=0)
    spend: Mapped[float] = mapped_column(Float, default=0)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | import
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    placement_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    markdown: Mapped[str] = mapped_column(Text, default="")
    structured_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="final")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(20))  # product | sku_stock | metric
    filename: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="previewed")
    mapping_json: Mapped[dict] = mapped_column(JSON, default=dict)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ImportError(Base):
    __tablename__ = "import_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    row_no: Mapped[int] = mapped_column(Integer, default=0)
    field: Mapped[str] = mapped_column(String(100), default="")
    message: Mapped[str] = mapped_column(String(500), default="")
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SystemConfig(Base):
    __tablename__ = "system_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
