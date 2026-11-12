from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from ..models import MetricRecord, Placement, Product, Sku, Store
from ..security import CurrentUser, DbSession
from ..services.lifecycle import STAGE_LABELS, product_stage
from ..services.service_profiles import SERVICE_CATEGORIES

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _metric_sums(db, start: str):
    rows = db.execute(
        select(
            MetricRecord.date,
            func.sum(MetricRecord.gmv),
            func.sum(MetricRecord.spend),
            func.sum(MetricRecord.orders),
            func.sum(MetricRecord.impressions),
        )
        .where(MetricRecord.date >= start)
        .group_by(MetricRecord.date)
        .order_by(MetricRecord.date)
    ).all()
    return {
        r[0]: {
            "gmv": float(r[1] or 0),
            "spend": float(r[2] or 0),
            "orders": int(r[3] or 0),
            "impressions": int(r[4] or 0),
        }
        for r in rows
    }


@router.get("/summary")
def summary(db: DbSession, _: CurrentUser):
    today = date.today()
    products = db.scalars(select(Product).where(Product.archived.is_(False))).all()
    total = len(products)

    warning_rows = db.execute(
        select(Sku, Product, Store)
        .join(Product, Product.id == Sku.product_id)
        .join(Store, Store.id == Product.store_id)
        .where(
            Product.category.notin_(SERVICE_CATEGORIES),
            Sku.stock <= Sku.warn_threshold,
        )
        .order_by(Sku.stock.asc())
        .limit(10)
    ).all()

    month_start = today - timedelta(days=29)
    metrics_30 = _metric_sums(db, month_start.isoformat())
    gmv_30 = sum(m["gmv"] for m in metrics_30.values())
    spend_30 = sum(m["spend"] for m in metrics_30.values())

    active_products = db.scalar(
        select(func.count(func.distinct(MetricRecord.product_id))).where(
            MetricRecord.date >= month_start.isoformat()
        )
    ) or 0
    on_sale_rate = round(active_products / total * 100, 1) if total else 0.0

    trend_start = today - timedelta(days=13)
    trend_metrics = _metric_sums(db, trend_start.isoformat())
    trend = []
    for i in range(14):
        d = (trend_start + timedelta(days=i)).isoformat()
        m = trend_metrics.get(d)
        trend.append(
            {
                "date": d,
                "gmv": round(m["gmv"], 2) if m else 0,
                "orders": m["orders"] if m else 0,
                "roi": round(m["gmv"] / m["spend"], 2) if m and m["spend"] else 0,
            }
        )

    stores = db.scalars(select(Store).order_by(Store.id)).all()
    store_cards = []
    for store in stores:
        product_count = db.scalar(
            select(func.count(Product.id)).where(Product.store_id == store.id)
        ) or 0
        store_warning = db.scalar(
            select(func.count(Sku.id))
            .join(Product, Product.id == Sku.product_id)
            .where(
                Product.store_id == store.id,
                Product.category.notin_(SERVICE_CATEGORIES),
                Sku.stock <= Sku.warn_threshold,
            )
        ) or 0
        store_cards.append(
            {
                "id": store.id,
                "name": store.name,
                "platform": store.platform,
                "auth_status": store.auth_status,
                "product_count": product_count,
                "stock_warning_count": store_warning,
            }
        )

    pending_approvals = db.scalar(
        select(func.count(Placement.id)).where(Placement.status == "pending_approval")
    ) or 0

    return {
        "kpis": {
            "product_total": total,
            "on_sale_rate": on_sale_rate,
            "active_products": active_products,
            "stock_warning_count": len(warning_rows),
            "gmv_30d": round(gmv_30, 2),
            "roi_30d": round(gmv_30 / spend_30, 2) if spend_30 else 0,
            "pending_approvals": pending_approvals,
        },
        "stores": store_cards,
        "stock_warnings": [
            {
                "product_id": product.id,
                "product_name": product.name,
                "sku_id": sku.id,
                "spec": sku.spec_json,
                "stock": sku.stock,
                "threshold": sku.warn_threshold,
                "store_name": store.name,
                "stage": product_stage(db, product.id),
                "stage_label": STAGE_LABELS[product_stage(db, product.id)],
            }
            for sku, product, store in warning_rows
        ],
        "trend": trend,
    }
