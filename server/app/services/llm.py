"""LLM 双通道服务：真实接口 + 确定性 Mock。

- 默认读取 system_configs["llm"]，未配置时使用 Mock 通道。
- 真实通道支持 Anthropic Messages API，也保留 OpenAI 兼容协议。
- 所有输出都必须通过 Pydantic Schema 校验；真实通道失败自动回退 Mock。
- 严禁在日志或响应中输出 API Key。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SystemConfig
from .service_profiles import get_service_profile

DEFAULT_LLM_CONFIG = {
    "mode": "mock",
    "provider": "anthropic",
    "base_url": "",
    "api_key": "",
    "model": "claude-sonnet-5-5",
    "temperature": 0.7,
    "timeout_seconds": 60,
}

PLATFORM_ALIASES = {
    "淘宝": "taobao",
    "天猫": "taobao",
    "taobao": "taobao",
    "tmall": "taobao",
    "京东": "jd",
    "jd": "jd",
    "抖音": "douyin",
    "抖店": "douyin",
    "douyin": "douyin",
    "拼多多": "pdd",
    "pdd": "pdd",
    "本地生活": "local",
    "美团": "local",
    "大众点评": "local",
    "local": "local",
}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class Audience(BaseModel):
    persona: str
    needs: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)


class PriceAnalysis(BaseModel):
    position: str
    competitor_range: str
    suggestion: str


class SellingPoint(BaseModel):
    point: str
    evidence: str
    diff: str


class DiagnosisContent(BaseModel):
    audience: Audience
    price_analysis: PriceAnalysis
    selling_points: list[SellingPoint] = Field(default_factory=list)
    conversion_blockers: list[str] = Field(default_factory=list)
    optimization_directions: list[str] = Field(default_factory=list)


class CompetitorDraft(BaseModel):
    platform: str = "taobao"
    name: str
    price: float = 0
    url: str = ""
    params_json: dict[str, str] = Field(default_factory=dict)
    sales_volume: int = 0
    rating: float = 0
    source: str = "ai_parse"
    parse_status: str = "draft"


class CompetitorParseResult(BaseModel):
    drafts: list[CompetitorDraft] = Field(default_factory=list)


class CreativeImageScheme(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    layout: str
    copy_text: str = Field(alias="copy")
    main_selling_point: str
    visual_tip: str


class CreativeShot(BaseModel):
    duration_sec: int = Field(default=3, ge=1, le=60)
    scene_desc: str
    voiceover: str = ""
    cta_line: str = ""


class CreativeVideoScript(BaseModel):
    title: str
    hook_3s: str
    closing_cta: str
    shots: list[CreativeShot] = Field(default_factory=list)


class CreativePlanContent(BaseModel):
    image_schemes: list[CreativeImageScheme] = Field(default_factory=list)
    video_scripts: list[CreativeVideoScript] = Field(default_factory=list)


SCHEMAS: dict[str, type[BaseModel]] = {
    "diagnosis": DiagnosisContent,
    "competitor_parse": CompetitorParseResult,
    "creative_plan": CreativePlanContent,
}


@dataclass
class LLMResult:
    content: dict
    channel: str  # mock | real | mock_fallback
    model: str
    note: str = ""
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------


def get_llm_config(db: Session) -> dict:
    row = db.scalar(select(SystemConfig).where(SystemConfig.key == "llm"))
    config = dict(DEFAULT_LLM_CONFIG)
    if row and isinstance(row.value_json, dict):
        config.update(row.value_json)
    return config


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------


def generate_structured(db: Session, task_type: str, context: dict) -> LLMResult:
    """按任务类型生成结构化内容，返回实际使用通道。"""
    if task_type not in SCHEMAS:
        raise ValueError(f"不支持的任务类型：{task_type}")

    cfg = get_llm_config(db)
    if cfg.get("mode") != "real":
        content = _mock_content(task_type, context)
        return LLMResult(
            content=content,
            channel="mock",
            model=f"mock-{task_type}-v1",
            note="当前为确定性 Mock 通道，可在系统配置中切换真实接口。",
        )

    try:
        raw = _call_real(cfg, task_type, context)
        validated = SCHEMAS[task_type].model_validate(raw)
        return LLMResult(
            content=validated.model_dump(by_alias=True),
            channel="real",
            model=str(cfg.get("model") or "real"),
            note="已通过真实模型接口生成。",
        )
    except Exception as exc:  # 真实通道失败统一回退 Mock
        content = _mock_content(task_type, context)
        reason = _safe_error(exc)
        return LLMResult(
            content=content,
            channel="mock_fallback",
            model=f"mock-{task_type}-v1 (fallback)",
            note="真实接口调用失败，已自动回退 Mock 通道。",
            warnings=[reason],
        )


def validate_content(task_type: str, content: dict) -> dict:
    return SCHEMAS[task_type].model_validate(content).model_dump(by_alias=True)


def mock_content(task_type: str, context: dict) -> dict:
    """公开的确定性 Mock 内容，供创意补足等场景复用。"""
    return _mock_content(task_type, context)


# ---------------------------------------------------------------------------
# 真实通道
# ---------------------------------------------------------------------------


def _safe_error(exc: Exception) -> str:
    text = str(exc)
    text = re.sub(r"(sk-[A-Za-z0-9_\-]+)", "sk-***", text)
    text = re.sub(r"(Bearer\s+)[^\s\"']+", r"\1***", text, flags=re.I)
    return text[:300]


def _service_prompt_block(context: dict) -> str:
    profile = context.get("service_profile") or {}
    if not profile:
        return ""
    packages = "；".join(
        f"{item.get('name')} {item.get('pricing')}" for item in (profile.get("packages") or [])
    )
    return (
        "\n\n该业务为本地生活服务（非实物商品），必须遵循服务口径：\n"
        f"- 品类：{profile.get('category')}；价格单位：{profile.get('price_unit')}；"
        f"业务定位：{profile.get('business_name')}\n"
        f"- 服务套餐：{packages}\n"
        f"- 目标人群：{profile.get('persona')}\n"
        f"- 信任点：{'、'.join(profile.get('trust_points') or [])}\n"
        f"- 可用 CTA：{'、'.join(profile.get('ctas') or [])}\n"
        f"- 合规口径：{profile.get('claim_guidance')}；"
        f"禁用表述：{'、'.join(profile.get('forbidden_claims') or [])}\n"
        "- 禁止出现快递、发货、实物库存等实物商品表述；服务范围、计价方式与预约动作要写清楚。\n"
    )


def _prompt(task_type: str, context: dict) -> tuple[str, str]:
    context_text = json.dumps(context, ensure_ascii=False, indent=2)
    service_block = _service_prompt_block(context)
    if task_type == "diagnosis":
        system = (
            "你是资深电商与本地生活运营诊断专家。请基于商品、SKU、竞品与历史复盘信息输出中文结构化诊断。"
            "只输出一个 JSON 对象，不要 Markdown 代码块。字段必须为："
            "audience{persona,needs[],scenarios[]}、"
            "price_analysis{position,competitor_range,suggestion}、"
            "selling_points[{point,evidence,diff}]、"
            "conversion_blockers[]、optimization_directions[]。"
            "内容要具体、可执行，避免空泛套话。"
            + service_block
        )
        user = f"诊断上下文：\n{context_text}\n\n请输出诊断 JSON。"
        return system, user

    if task_type == "creative_plan":
        system = (
            "你是资深电商内容创意总监。请基于诊断结论输出可直接执行的主图方案与短视频分镜脚本。"
            "只输出一个 JSON 对象，不要 Markdown 代码块。字段必须为："
            "image_schemes[{title,layout,copy,main_selling_point,visual_tip}]（至少 3 组）、"
            "video_scripts[{title,hook_3s,closing_cta,shots:[{duration_sec,scene_desc,voiceover,cta_line}]}]"
            "（至少 3 套，每套至少 4 个分镜）。"
            "文案要具体、有画面感、可直接拍摄，避免空泛口号；沿用诊断中的卖点与人群场景。"
            + service_block
            + (
                "服务业务请输出「获客素材方案」与本地生活短视频脚本，"
                "CTA 必须使用服务预约 / 领取方案 / 团购券等动作，素材模板按品类区分。"
                if service_block
                else ""
            )
        )
        user = f"创意上下文：\n{context_text}\n\n请输出创意方案 JSON。"
        return system, user

    system = (
        "你是电商竞品信息抽取助手。从用户粘贴的商品文本中抽取竞品结构化信息。"
        "只输出一个 JSON 对象，不要 Markdown 代码块，格式为："
        '{"drafts":[{"platform":"taobao|jd|douyin|pdd","name":"","price":0,'
        '"url":"","params_json":{},"sales_volume":0,"rating":0,'
        '"source":"ai_parse","parse_status":"draft"}]}。'
        "缺失的字段使用空字符串、0 或空对象。"
    )
    user = f"待解析文本：\n{context.get('text', '')}\n\n商品上下文：\n{context_text}\n\n请输出抽取结果 JSON。"
    return system, user


def _call_real(cfg: dict, task_type: str, context: dict) -> dict:
    provider = str(cfg.get("provider") or "anthropic").lower()
    system, user = _prompt(task_type, context)
    if provider in {"openai", "openai_compatible", "compatible"}:
        text = _call_openai(cfg, system, user)
    else:
        text = _call_anthropic(cfg, system, user)
    return _extract_json(text)


def _call_anthropic(cfg: dict, system: str, user: str) -> str:
    base_url = (cfg.get("base_url") or os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
    api_key = cfg.get("api_key") or os.getenv("ANTHROPIC_AUTH_TOKEN") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("未配置真实接口的 API Key")

    url = base_url if base_url.endswith("/v1/messages") else f"{base_url}/v1/messages"
    headers = {
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
        "x-api-key": api_key,
        "authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": cfg.get("model") or "claude-sonnet-5-5",
        "max_tokens": 2400,
        "temperature": float(cfg.get("temperature") or 0.7),
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    with httpx.Client(timeout=float(cfg.get("timeout_seconds") or 60)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    blocks = data.get("content") or []
    texts = [b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    if not texts:
        raise RuntimeError("真实接口未返回文本内容")
    return "\n".join(texts)


def _call_openai(cfg: dict, system: str, user: str) -> str:
    base_url = (cfg.get("base_url") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    api_key = cfg.get("api_key") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 OpenAI 兼容接口的 API Key")
    url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
    headers = {"content-type": "application/json", "authorization": f"Bearer {api_key}"}
    payload = {
        "model": cfg.get("model") or "gpt-4o-mini",
        "temperature": float(cfg.get("temperature") or 0.7),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    with httpx.Client(timeout=float(cfg.get("timeout_seconds") or 60)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI 兼容接口未返回候选内容")
    return choices[0].get("message", {}).get("content", "")


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型输出不包含 JSON 对象")
    return json.loads(text[start : end + 1])


# ---------------------------------------------------------------------------
# 确定性 Mock
# ---------------------------------------------------------------------------


def _mock_content(task_type: str, context: dict) -> dict:
    if task_type == "competitor_parse":
        return _mock_competitor_parse(context)
    profile = context.get("service_profile") or get_service_profile(
        (context.get("product") or {}).get("category")
    )
    if profile:
        if task_type == "creative_plan":
            return _mock_service_creative(context, profile)
        return _mock_service_diagnosis(context, profile)
    if task_type == "creative_plan":
        return _mock_creative(context)
    return _mock_diagnosis(context)


def _detect_platform(text: str) -> str:
    lowered = text.lower()
    for key, value in PLATFORM_ALIASES.items():
        if key in text or key in lowered:
            return value
    return "taobao"


def _to_number(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mock_competitor_parse(context: dict) -> dict:
    text = str(context.get("text") or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = lines[0] if lines else ""
    name = re.split(r"[|｜,，;；]", first_line)[0].strip() or "待命名竞品"
    name = re.sub(r"^(淘宝|天猫|京东|抖音|拼多多)[:：\s]*", "", name)

    price = 0.0
    price_match = re.search(r"(?:¥|￥)\s*(\d+(?:\.\d+)?)", text) or re.search(
        r"(?:价格|售价|到手价)[:：]?\s*(\d+(?:\.\d+)?)", text
    )
    if price_match:
        price = _to_number(price_match.group(1))

    sales_volume = 0
    sales_match = re.search(r"(?:月销|销量|已售)[:：]?\s*([\d.]+)\s*(万)?", text)
    if sales_match:
        sales_volume = int(_to_number(sales_match.group(1)) * (10000 if sales_match.group(2) else 1))

    rating = 0.0
    rating_match = re.search(r"(?:评分|好评率|星级)[:：]?\s*([\d.]+)", text)
    if rating_match:
        rating = _to_number(rating_match.group(1))

    url_match = re.search(r"https?://[^\s，,；;]+", text)
    url = url_match.group(0) if url_match else ""

    params: dict[str, str] = {}
    for match in re.finditer(r"([一-龥A-Za-z][一-龥A-Za-z0-9 ]{0,12})[:：]\s*([^,，;；|｜\n]{1,40})", text):
        key = match.group(1).strip()
        value = match.group(2).strip()
        if key in {"价格", "售价", "到手价", "月销", "销量", "已售", "评分", "好评率", "星级", "平台"}:
            continue
        if key.lower() in {"http", "https", "url", "链接"} or value.startswith("//"):
            continue
        if value:
            params[key] = value

    # 常见没有冒号的参数，做一条兜底
    if not params:
        known = re.findall(r"(UPF\s*\d+\+?|原纱型|涂层型|冰丝|石墨烯|主动降噪|\d+W|\d+\s*mAh)", text)
        if known:
            params["关键参数"] = " / ".join(dict.fromkeys(known))

    draft = CompetitorDraft(
        platform=_detect_platform(text),
        name=name,
        price=price,
        url=url,
        params_json=params,
        sales_volume=sales_volume,
        rating=rating,
        source="ai_parse",
        parse_status="draft",
    )
    return {"drafts": [draft.model_dump()]}


CATEGORY_PROFILES: dict[str, dict] = {
    "防晒服饰": {
        "persona": "18-35 岁通勤、骑行与轻户外人群，夏季长时间暴露在紫外线下，既在意防晒效果，也在意闷热与版型",
        "needs": ["UPF50+ 有效防晒", "冰感透气不闷汗", "版型显瘦易搭配"],
        "scenarios": ["通勤骑行", "周末轻户外", "开车防晒"],
    },
    "数码配件": {
        "persona": "22-35 岁数码爱好者与通勤白领，手机使用时长高，关注充电效率、温控与桌面整洁度",
        "needs": ["快充不伤电池", "边充边用不发烫", "轻便易携带"],
        "scenarios": ["办公室桌面", "床头夜充", "差旅随身"],
    },
    "厨房小电": {
        "persona": "22-35 岁注重健康饮食的都市女性与带娃家庭，追求省时、易清洗与便携",
        "needs": ["操作省时", "清洗方便", "出汁细腻"],
        "scenarios": ["早餐", "办公室", "露营"],
    },
}


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。；;]", text or "") if part.strip()]


def _mock_diagnosis(context: dict) -> dict:
    product = context.get("product") or {}
    skus = context.get("skus") or []
    competitors = context.get("competitors") or []
    action_items = [str(x).strip() for x in (context.get("action_items") or []) if str(x).strip()]

    category = str(product.get("category") or "")
    profile = CATEGORY_PROFILES.get(category)
    if profile is None:
        profile = {
            "persona": f"{category or '该品类'}的目标消费人群，关注产品实际效果、价格合理性与使用便利性",
            "needs": ["核心功能可靠", "价格有竞争力", "使用体验省心"],
            "scenarios": ["日常使用", "通勤出行", "礼物/替换需求"],
        }

    prices = [float(s.get("price") or 0) for s in skus if float(s.get("price") or 0) > 0]
    own_min = min(prices) if prices else float(product.get("price_min") or 0)
    own_max = max(prices) if prices else float(product.get("price_max") or 0)
    own_avg = round(sum(prices) / len(prices), 2) if prices else round((own_min + own_max) / 2, 2)
    stock_total = sum(int(s.get("stock") or 0) for s in skus)
    warning_skus = [s for s in skus if int(s.get("stock") or 0) <= int(s.get("warn_threshold") or 0)]

    comp_prices = [float(c.get("price") or 0) for c in competitors if float(c.get("price") or 0) > 0]
    comp_names = [str(c.get("name") or "") for c in competitors if c.get("name")]
    comp_desc = "、".join(comp_names[:3]) or "暂无竞品"
    if comp_prices:
        competitor_range = (
            f"{comp_desc}价格带 ¥{min(comp_prices):g}-{max(comp_prices):g}，"
            f"均价 ¥{sum(comp_prices) / len(comp_prices):.0f}"
        )
    else:
        competitor_range = "暂无有效竞品价格数据，建议补充 2-3 个直接竞品后再校准价格策略"

    position = (
        f"当前 SKU 价格带 ¥{own_min:g}-{own_max:g}（均价 ¥{own_avg:g}），"
        f"主销规格 {len(skus)} 个，库存合计 {stock_total} 件"
    )
    if comp_prices and min(comp_prices) < own_min * 0.9:
        suggestion = (
            f"竞品最低价 ¥{min(comp_prices):g} 已形成明显低价锚点，不建议正面跟价；"
            f"应围绕差异化卖点、赠品与履约体验守住 ¥{own_min:g} 价格带。"
        )
    elif comp_prices and own_avg > sum(comp_prices) / len(comp_prices):
        suggestion = "本品均价高于竞品均值，需在主图与详情页前置可验证的品质证据，降低用户比价流失。"
    else:
        suggestion = "当前价格具备竞争力，建议维持主价，通过组合装与限时赠品提升客单与转化。"

    desc_sentences = _split_sentences(str(product.get("description") or ""))
    core_evidence = desc_sentences[0] if desc_sentences else f"{product.get('name') or '本品'}的核心功能与品质保障"
    comp_param_text = ""
    if competitors:
        params = competitors[0].get("params_json") or {}
        if isinstance(params, dict) and params:
            comp_param_text = "；".join(f"{k} {v}" for k, v in list(params.items())[:4])
    selling_points = [
        {
            "point": "核心产品力可感知",
            "evidence": core_evidence,
            "diff": f"竞品参数：{comp_param_text}" if comp_param_text else "需在详情页补充竞品对比证据，强化差异感知",
        },
        {
            "point": "多规格覆盖更完整",
            "evidence": f"提供 {len(skus)} 个 SKU，价格覆盖 ¥{own_min:g}-{own_max:g}",
            "diff": "同价位竞品常见单一规格，难以覆盖不同偏好人群",
        },
        {
            "point": "价格带定位清晰",
            "evidence": f"主销均价 ¥{own_avg:g}，与竞品形成可解释的价差",
            "diff": competitor_range,
        },
    ]

    blockers: list[str] = []
    if comp_prices and min(comp_prices) < own_min:
        cheapest = min(competitors, key=lambda c: float(c.get("price") or 10**9))
        blockers.append(
            f"竞品「{cheapest.get('name')}」以 ¥{float(cheapest.get('price') or 0):g} 抢占比价场景，价格锚点被拉低"
        )
    if warning_skus:
        spec_text = "、".join(
            "/".join(str(v) for v in (s.get("spec_json") or {}).values()) or f"SKU{s.get('id')}"
            for s in warning_skus[:2]
        )
        blockers.append(f"{spec_text} 库存低于安全线，投放放量后存在断货与权重下滑风险")
    blockers.append("主图与详情页缺少量化实测证据（检测报告/对比数据），卖点可信度不足")
    blockers.append("场景化内容不足，用户从种草到搜索的决策链路偏长")

    directions: list[str] = []
    for item in action_items:
        if item not in directions:
            directions.append(item)
    if comp_prices and min(comp_prices) < own_min:
        directions.append("主图增加「价格 + 参数」对比模块，用可验证差异解释价差，避免直接降价")
    directions.append("详情页首屏补充 3 个量化证据（检测报告、实测数据、用户评价摘要）")
    directions.append("围绕 2 个高频使用场景制作短视频，缩短种草到搜索的转化链路")
    if warning_skus:
        directions.append("为低库存 SKU 制定补货计划，避免投放放量期间断货")
    directions = list(dict.fromkeys(directions))[:5]

    content = DiagnosisContent(
        audience=Audience(
            persona=str(profile["persona"]),
            needs=list(profile["needs"]),
            scenarios=list(profile["scenarios"]),
        ),
        price_analysis=PriceAnalysis(
            position=position,
            competitor_range=competitor_range,
            suggestion=suggestion,
        ),
        selling_points=[SellingPoint(**item) for item in selling_points],
        conversion_blockers=blockers[:4],
        optimization_directions=directions or ["补充竞品数据后重新生成诊断"],
    )
    return content.model_dump()


def _mock_service_diagnosis(context: dict, profile: dict) -> dict:
    """本地生活服务诊断：围绕套餐、信任点、预约与合规口径展开。"""
    product = context.get("product") or {}
    competitors = context.get("competitors") or []
    action_items = [str(x).strip() for x in (context.get("action_items") or []) if str(x).strip()]

    packages = list(profile.get("packages") or [])
    trust_points = list(profile.get("trust_points") or [])
    ctas = list(profile.get("ctas") or [])
    scenarios = list(profile.get("scenarios") or [])
    package_text = "；".join(
        f"{item.get('name')} {item.get('pricing')}" for item in packages
    ) or "按现场情况报价"
    scene = scenarios[0] if scenarios else "本地生活服务场景"

    comp_prices = [float(c.get("price") or 0) for c in competitors if float(c.get("price") or 0) > 0]
    comp_names = [str(c.get("name") or "") for c in competitors if c.get("name")]
    comp_desc = "、".join(comp_names[:3]) or "暂无竞品"
    if comp_prices:
        competitor_range = (
            f"{comp_desc}价格带 ¥{min(comp_prices):g}-{max(comp_prices):g}，"
            f"均价 ¥{sum(comp_prices) / len(comp_prices):.0f}"
        )
    else:
        competitor_range = "暂无本地竞品价格数据，建议补充美团 / 大众点评竞品后再校准套餐价"

    position = (
        f"{profile['category']}，核心套餐：{package_text}；"
        f"计价单位 {profile['price_unit']}，主要服务场景：{'、'.join(scenarios) or scene}"
    )
    suggestion = (
        f"检测 / 洗护与治理 / 取送分项报价，不以低价引流后加价；"
        f"统一使用「{profile['claim_guidance']}」解释套餐价差。"
    )

    point_labels = ["信任背书", "过程保障", "场景适配"]
    selling_points: list[dict] = []
    for index, trust in enumerate((trust_points + ["上门服务流程可追溯"])[:3]):
        package = packages[index] if index < len(packages) else None
        selling_points.append(
            {
                "point": f"{point_labels[index]}：{trust}",
                "evidence": (
                    f"套餐「{package.get('name')}」{package.get('pricing')}，{package.get('description')}"
                    if package
                    else f"服务场景：{scene}"
                ),
                "diff": (
                    f"本地竞品：{comp_desc}；需在获客素材中前置可验证记录"
                    if competitors
                    else "本地竞品信息不足，建议补充 2 家直接竞品"
                ),
            }
        )
    while len(selling_points) < 3:
        selling_points.append(
            {
                "point": f"服务标准化：{profile['claim_guidance']}",
                "evidence": package_text,
                "diff": competitor_range,
            }
        )

    first_category = str(profile.get("category") or "")
    if first_category == "除甲醛服务":
        price_blocker = "用户担心检测数据不真实，低价检测后治理增项，价格锚点被打乱"
        service_blocker = "母婴家庭对入住时间敏感，治理与复检周期必须提前说清"
    else:
        price_blocker = "用户担心洗护过程不透明，低价引流后按件加价，价格锚点被打乱"
        service_blocker = "换季集中送洗，取送时效与异常件责任划分必须提前说清"

    blockers = [
        price_blocker,
        service_blocker,
        f"{scene}预约集中，用户担心上门时段与服务容量，容易在预约环节流失",
        "服务前后缺少可验证记录，复购与转介绍依赖口头承诺",
    ]

    directions: list[str] = []
    for item in action_items:
        if item not in directions:
            directions.append(item)
    directions.append(f"获客素材前置「{trust_points[0] if trust_points else profile['claim_guidance']}」与套餐价目")
    directions.append(f"用「{scene}」场景解释{packages[0].get('name') if packages else '核心套餐'}与价格差异")
    if ctas:
        directions.append(f"所有获客素材统一使用预约动作「{ctas[0]}」")
    directions.append(f"合规口径统一为：{profile['claim_guidance']}")
    directions = list(dict.fromkeys(directions))[:5]

    content = DiagnosisContent(
        audience=Audience(
            persona=str(profile.get("persona") or ""),
            needs=list(profile.get("needs") or []),
            scenarios=scenarios,
        ),
        price_analysis=PriceAnalysis(
            position=position,
            competitor_range=competitor_range,
            suggestion=suggestion,
        ),
        selling_points=[SellingPoint(**item) for item in selling_points],
        conversion_blockers=blockers[:4],
        optimization_directions=directions or ["补充本地竞品与套餐数据后重新生成诊断"],
    )
    return content.model_dump()


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned if len(cleaned) <= limit else f"{cleaned[:limit]}…"


def _mock_creative(context: dict) -> dict:
    """基于诊断内容生成确定性的主图方案与分镜脚本，保证 ≥3 组、每组 ≥4 镜。"""
    product = context.get("product") or {}
    diagnosis = context.get("diagnosis") or {}
    audience = diagnosis.get("audience") or {}
    price_analysis = diagnosis.get("price_analysis") or {}

    name = str(product.get("name") or "本品")
    category = str(product.get("category") or "商品")
    price_min = float(product.get("price_min") or 0)
    price_max = float(product.get("price_max") or 0)
    price_band = (
        f"¥{price_min:g}-{price_max:g}" if price_max and price_max != price_min else f"¥{price_min:g}"
    )

    needs = [str(x).strip() for x in (audience.get("needs") or []) if str(x).strip()]
    scenes = [str(x).strip() for x in (audience.get("scenarios") or []) if str(x).strip()]
    needs = needs or ["核心功能可靠", "体验省心", "价格合理"]
    scenes = scenes or ["日常使用", "通勤出行", "居家场景"]

    raw_points = [
        item
        for item in (diagnosis.get("selling_points") or [])
        if isinstance(item, dict) and str(item.get("point") or "").strip()
    ]
    fallback_points = [
        {"point": "核心产品力", "evidence": f"{name}的核心功能与品质保障", "diff": "需补充竞品对比数据"},
        {"point": "多规格覆盖", "evidence": f"覆盖 {price_band} 价格带，适配不同需求", "diff": "同价位竞品规格相对单一"},
        {"point": "场景适配", "evidence": f"适合{scenes[0]}等高频场景", "diff": "竞品场景化内容较少"},
    ]
    points = [
        {
            "point": str(item.get("point") or "").strip(),
            "evidence": str(item.get("evidence") or "").strip() or "需补充可验证证据",
            "diff": str(item.get("diff") or "").strip() or "需补充竞品差异",
        }
        for item in raw_points[:3]
    ]
    while len(points) < 3:
        points.append(fallback_points[len(points)])

    blockers = [str(x).strip() for x in (diagnosis.get("conversion_blockers") or []) if str(x).strip()]
    directions = [
        str(x).strip() for x in (diagnosis.get("optimization_directions") or []) if str(x).strip()
    ]
    suggestion = str(price_analysis.get("suggestion") or "").strip()

    p1, p2, p3 = points[0], points[1], points[2]

    image_schemes = [
        CreativeImageScheme(
            title="方向一：核心卖点直给",
            layout=(
                f"浅色极简背景，{name} 以 45° 居中悬浮，右侧叠加大字「{_clip(p1['point'], 14)}」，"
                f"下方用数据条展示「{_clip(p1['evidence'], 26)}」，左下角嵌入{scenes[0]}场景小图。"
            ),
            copy_text=f"{p1['point']}，{_clip(needs[0], 12)}",
            main_selling_point=f"{p1['point']}：{p1['evidence']}",
            visual_tip="沿用品牌青绿主色，信息块不超过 3 个；卖点文字使用高对比白字，数据标签做描边处理。",
        ),
        CreativeImageScheme(
            title="方向二：参数对比硬核",
            layout=(
                "左右分屏对比：左侧本品展示核心参数、实测数据与到手价，右侧列出竞品常见参数，"
                "中间用对勾与叉号强化差异，底部保留检测报告或实测截图。"
            ),
            copy_text=f"同样{price_band}，为什么要选{_clip(name, 12)}？",
            main_selling_point=f"{p2['point']}（{_clip(p2['evidence'], 28)}）",
            visual_tip="红蓝对比配色，参数表格化；只保留 3 组最关键差异，避免信息过载。",
        ),
        CreativeImageScheme(
            title="方向三：人群场景种草",
            layout=(
                f"{scenes[0]}实景构图，人物自然使用{name}，产品位于视觉中心，"
                f"右上角叠加「{_clip(needs[0], 12)}」标签，背景轻微虚化。"
            ),
            copy_text=f"{_clip(scenes[0], 8)}，也能{_clip(needs[0], 12)}",
            main_selling_point=f"{p3['point']}：{_clip(p3['evidence'], 28)}",
            visual_tip="自然光与低饱和生活方式配色，人物表情放松；保留产品细节，避免纯氛围图。",
        ),
    ]

    hook1 = (
        f"{scenes[0]}时，你是不是也遇到：{_clip(blockers[0], 24)}？"
        if blockers
        else f"{scenes[0]}，你真的选对{category}了吗？"
    )
    hook2 = (
        f"同样{price_band}，为什么有的{category}用半年就出问题？"
        if price_band
        else f"同样价位，为什么有的{category}更耐用？"
    )
    hook3 = f"如果{scenes[0]}只能带一件{category}，你会选什么？"

    closing1 = f"{_clip(suggestion, 22)}，点击购物车立即下单" if suggestion else "点击购物车，今天下单享限时赠品"
    closing2 = directions[0] if directions else "评论区扣「对比」，给你看完整实测数据"
    closing3 = "点击下方链接，限时赠送运费险"

    video_scripts = [
        CreativeVideoScript(
            title="脚本一：痛点开场",
            hook_3s=hook1,
            closing_cta=closing1,
            shots=[
                CreativeShot(
                    duration_sec=3,
                    scene_desc=f"特写：{scenes[0]}中暴露痛点的高频瞬间",
                    voiceover=hook1,
                    cta_line="先别急着下单",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc=f"中景：拿起{name}，展示{p1['point']}",
                    voiceover=f"这款{name}，{_clip(p1['evidence'], 30)}",
                    cta_line=p1["point"],
                ),
                CreativeShot(
                    duration_sec=6,
                    scene_desc="特写/实测：展示检测报告、对比数据或真实使用效果",
                    voiceover=_clip(p1["diff"], 32),
                    cta_line="差异看得见",
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc="口播：手持产品对准镜头，给出明确行动指令",
                    voiceover=f"{name}，{_clip(needs[0], 14)}，到手价 {price_band}",
                    cta_line="点击购物车立即下单",
                ),
            ],
        ),
        CreativeVideoScript(
            title="脚本二：实测对比硬核",
            hook_3s=hook2,
            closing_cta=closing2,
            shots=[
                CreativeShot(
                    duration_sec=3,
                    scene_desc="对比镜头：两款产品并排放在同一场景，价格标签同时入镜",
                    voiceover=hook2,
                    cta_line="别只看价格",
                ),
                CreativeShot(
                    duration_sec=6,
                    scene_desc=f"特写：拆解或展示本品关键结构，强调{p2['point']}",
                    voiceover=f"关键差异在这里：{_clip(p2['evidence'], 30)}",
                    cta_line="看得见的用料",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc="实拍：真实使用过程与效果对比，屏幕角标标注实测数据",
                    voiceover=_clip(p2["diff"], 32),
                    cta_line="效果自己会说话",
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc="口播：举起产品与竞品对比，指向购物车",
                    voiceover=f"{name}，{_clip(p2['point'], 16)}，现在下单更划算",
                    cta_line="点击下方链接",
                ),
            ],
        ),
        CreativeVideoScript(
            title="脚本三：场景种草",
            hook_3s=hook3,
            closing_cta=closing3,
            shots=[
                CreativeShot(
                    duration_sec=3,
                    scene_desc=f"全景：{scenes[0]}的真实环境，人物自然入镜",
                    voiceover=hook3,
                    cta_line="看看我的选择",
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc=f"中景：人物使用{name}，表情放松，突出{needs[0]}",
                    voiceover=f"{scenes[0]}带上它，{_clip(needs[0], 14)}",
                    cta_line="用起来很省心",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc=f"特写：产品细节与材质，叠加「{_clip(p3['point'], 12)}」角标",
                    voiceover=_clip(p3["evidence"], 32),
                    cta_line=p3["point"],
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc="口播：人物面对镜头总结体验，画面下方出现购买入口",
                    voiceover=f"{name}，{_clip(scenes[0], 10)}的好搭子",
                    cta_line=closing3,
                ),
            ],
        ),
    ]

    content = CreativePlanContent(image_schemes=image_schemes, video_scripts=video_scripts)
    return content.model_dump(by_alias=True)


def _mock_service_creative(context: dict, profile: dict) -> dict:
    """本地生活服务创意：输出获客素材方案与可拍摄短视频脚本。"""
    product = context.get("product") or {}
    name = str(product.get("name") or profile.get("category") or "服务项目")
    packages = list(profile.get("packages") or [])
    trust_points = list(profile.get("trust_points") or [])
    ctas = list(profile.get("ctas") or ["预约服务"])
    scenarios = list(profile.get("scenarios") or ["本地生活场景"])
    keywords = list(profile.get("keywords") or [])
    scene = scenarios[0] if scenarios else "本地生活场景"
    package_text = "；".join(
        f"{item.get('name')} {item.get('pricing')}" for item in packages
    ) or "按现场情况报价"
    trust_line = "；".join(trust_points[:3]) or profile.get("claim_guidance") or "服务流程可追溯"
    first_package = packages[0] if packages else {"name": "核心套餐", "pricing": "按需报价", "description": ""}
    second_package = packages[1] if len(packages) > 1 else first_package
    primary_cta = ctas[0]
    secondary_cta = ctas[1] if len(ctas) > 1 else primary_cta
    third_cta = ctas[2] if len(ctas) > 2 else secondary_cta
    claim_first = str(profile.get("claim_guidance") or "").split("、")[0] or "服务过程可追溯"
    template = profile.get("visual_template") or "service"

    image_schemes = [
        CreativeImageScheme(
            title="获客方向一：信任背书",
            layout=(
                f"{scene}实景构图，人物自然入镜；画面左侧突出「{trust_points[0] if trust_points else trust_line}」"
                f"与「{trust_points[1] if len(trust_points) > 1 else claim_first}」，右侧放套餐价目卡"
                f"「{first_package.get('name')} {first_package.get('pricing')}」，底部留预约入口。"
            ),
            copy_text=str(profile.get("hero_copy") or f"{trust_line}，{primary_cta}"),
            main_selling_point=f"{trust_line}",
            visual_tip=(
                f"使用 {template} 服务模板，主色清爽明亮；信息块不超过 3 个，"
                "素材固定标注「模拟生成，仅供方案评审」。"
            ),
        ),
        CreativeImageScheme(
            title="获客方向二：套餐与价格透明",
            layout=(
                f"三宫格价目对比，分别展示 {package_text}；每格标注适用场景与预约时效，"
                f"底部统一叠加「{primary_cta}」按钮。"
            ),
            copy_text=f"{second_package.get('name')} {second_package.get('pricing')}，{primary_cta}",
            main_selling_point=f"套餐透明：{package_text}",
            visual_tip=(
                "价目卡使用高对比数字与单位，避免低价引流后加价；"
                f"场景标签分别对应 {'、'.join(scenarios) or scene}。"
            ),
        ),
        CreativeImageScheme(
            title="获客方向三：场景痛点",
            layout=(
                f"{scene}痛点场景与服务前后对比，人物表情自然；角落标注"
                f"「{trust_points[2] if len(trust_points) > 2 else claim_first}」，"
                f"画面下方保留「{primary_cta}」入口。"
            ),
            copy_text=f"{scene}，{claim_first}",
            main_selling_point=f"{trust_points[2] if len(trust_points) > 2 else trust_line}",
            visual_tip=(
                "生活方式摄影风格，低饱和暖色；展示服务动作与真实记录，"
                f"避免绝对化表述，统一使用合规口径：{profile.get('claim_guidance')}。"
            ),
        ),
    ]

    video_scripts = [
        CreativeVideoScript(
            title="脚本一：场景痛点开场",
            hook_3s=f"{scene}，你是不是也担心{keywords[0] if keywords else '服务'}不够透明？",
            closing_cta=f"{primary_cta}，先看方案再决定",
            shots=[
                CreativeShot(
                    duration_sec=3,
                    scene_desc=f"痛点场景：{scene}的真实环境，人物面对镜头说出顾虑",
                    voiceover=f"{scene}，你是不是也担心{keywords[0] if keywords else '服务'}不够透明？",
                    cta_line="先别急着下单",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc=f"服务流程：上门 / 到店过程实拍，展示{trust_points[0] if trust_points else claim_first}",
                    voiceover=f"{name}，{trust_line}，每一步都可查",
                    cta_line="过程看得见",
                ),
                CreativeShot(
                    duration_sec=6,
                    scene_desc=f"套餐与价格：价目卡特写，逐项展示{package_text}",
                    voiceover=f"套餐明码标价：{package_text}，不低价引流后加价",
                    cta_line="价格透明",
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc="口播：人物面对镜头给出明确行动指令，画面下方出现预约入口",
                    voiceover=f"{scene}，{primary_cta}",
                    cta_line=primary_cta,
                ),
            ],
        ),
        CreativeVideoScript(
            title="脚本二：信任与过程",
            hook_3s=f"同样是{profile.get('category')}，为什么价格差这么多？",
            closing_cta=secondary_cta,
            shots=[
                CreativeShot(
                    duration_sec=3,
                    scene_desc="对比镜头：两家服务报价单并排，突出套餐与计价单位差异",
                    voiceover=f"同样是{profile.get('category')}，为什么价格差这么多？",
                    cta_line="别只看低价",
                ),
                CreativeShot(
                    duration_sec=6,
                    scene_desc=f"特写：展示{trust_points[0] if trust_points else claim_first}与过程记录",
                    voiceover=f"关键差异在这里：{trust_line}",
                    cta_line="信任有依据",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc=f"实拍：{scene}服务过程与前后对比，屏幕角标标注预约时效",
                    voiceover=f"{claim_first}，预约前先说清服务范围与时效",
                    cta_line="预约前先确认",
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc="口播：手持服务记录与价目卡，指向预约入口",
                    voiceover=f"{name}，{secondary_cta}",
                    cta_line=secondary_cta,
                ),
            ],
        ),
        CreativeVideoScript(
            title="脚本三：套餐怎么选",
            hook_3s=f"{scene}，到底该选哪个套餐？",
            closing_cta=third_cta,
            shots=[
                CreativeShot(
                    duration_sec=3,
                    scene_desc=f"全景：{scene}场景，人物面对多个套餐选项",
                    voiceover=f"{scene}，到底该选哪个套餐？",
                    cta_line="30 秒说清",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc=f"中景：逐项展示{package_text}，标注适用人群与场景",
                    voiceover=f"按场景选：{package_text}",
                    cta_line="按需选择",
                ),
                CreativeShot(
                    duration_sec=5,
                    scene_desc=f"特写：展示{trust_points[1] if len(trust_points) > 1 else claim_first}与复购评价",
                    voiceover=f"{trust_line}，做完还有记录可查",
                    cta_line="复购有保障",
                ),
                CreativeShot(
                    duration_sec=4,
                    scene_desc="口播：人物面对镜头总结选择理由，画面下方出现预约按钮",
                    voiceover=f"{name}，{third_cta}",
                    cta_line=third_cta,
                ),
            ],
        ),
    ]

    content = CreativePlanContent(image_schemes=image_schemes, video_scripts=video_scripts)
    return content.model_dump(by_alias=True)
