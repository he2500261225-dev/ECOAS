"""本地生活服务集中配置：品类白名单、套餐、信任点、CTA 与合规口径。

服务业务复用实物商品的表结构与闭环流程，不新增 business_type 字段。
未命中白名单的品类继续按实物商品处理。
"""

from __future__ import annotations

SERVICE_PROFILES: dict[str, dict] = {
    "除甲醛服务": {
        "category": "除甲醛服务",
        "short_name": "除甲醛",
        "business_name": "本地生活 · 空气治理",
        "price_unit": "元/㎡",
        "persona": (
            "新装修 3-12 个月的业主与备孕 / 母婴家庭，关注甲醛检测数据、治理效果的可持续性，"
            "以及治理后的复检与质保保障"
        ),
        "needs": ["检测数据可追溯", "按空间定制治理方案", "复检与质保"],
        "scenarios": ["新房入住前", "母婴急住", "旧房翻新"],
        "packages": [
            {
                "name": "全屋检测",
                "pricing": "¥299 / 3 点",
                "description": "上门采样 3 个点位，出具检测数据与污染源说明。",
            },
            {
                "name": "全屋治理",
                "pricing": "¥45 / ㎡",
                "description": "按户型、板材与污染源定制药剂与施工工艺。",
            },
            {
                "name": "母婴急住治理",
                "pricing": "¥68 / ㎡",
                "description": "母婴家庭加急方案，治理后复检合格再安排入住。",
            },
        ],
        "trust_points": ["第三方 CMA 检测报告", "治理后复检", "质保期内免费返工", "异常点位再次上门"],
        "ctas": ["预约免费检测", "领取全屋治理方案", "预约复检"],
        "visual_template": "clean-air",
        "forbidden_claims": ["零甲醛", "100% 去除", "永久有效"],
        "claim_guidance": "检测数据说话、按空间定制方案、复检与质保",
        "keywords": ["检测", "复检", "质保", "预约"],
        "hero_copy": "先检测，再治理，复检合格更安心",
    },
    "洗衣服务": {
        "category": "洗衣服务",
        "short_name": "洗衣",
        "business_name": "本地生活 · 洗护取送",
        "price_unit": "元/件起",
        "persona": (
            "25-40 岁都市上班族与有孩家庭，换季衣物、鞋履与床品清洗需求集中，"
            "重视上门取送的便利性与按面料洗护的安全性"
        ),
        "needs": ["上门取送省时", "按面料标识洗护", "异常件先沟通"],
        "scenarios": ["换季羽绒服", "运动鞋清洗", "床品四件套"],
        "packages": [
            {"name": "洗鞋", "pricing": "¥29 / 双", "description": "运动鞋、帆布鞋清洗，鞋面与鞋底分步处理。"},
            {"name": "羽绒服清洗", "pricing": "¥49 / 件", "description": "按洗标与面料标识洗护，长短款同价。"},
            {"name": "四件套清洗", "pricing": "¥69 / 套", "description": "床单、被套、枕套整套洗护，独立包装送回。"},
        ],
        "trust_points": [
            "满 ¥99 上门取送免运费",
            "按面料标识洗护",
            "异常件先沟通",
            "超时赔付按门店规则",
        ],
        "ctas": ["预约上门取送", "领取洗护团购券", "查看洗护价目"],
        "visual_template": "laundry-care",
        "forbidden_claims": ["100% 洗净", "绝对不伤衣"],
        "claim_guidance": "按面料标识洗护、异常件先沟通、超时赔付按门店规则",
        "keywords": ["洗护", "取送", "上门"],
        "hero_copy": "满 ¥99 上门取送，按面料标识洗护",
    },
}

SERVICE_CATEGORIES: tuple[str, ...] = tuple(SERVICE_PROFILES.keys())


def get_service_profile(category: str | None) -> dict | None:
    """按品类返回服务配置；非服务品类返回 None。"""
    return SERVICE_PROFILES.get((category or "").strip())


def is_service_category(category: str | None) -> bool:
    return get_service_profile(category) is not None


def price_unit_for(category: str | None) -> str:
    profile = get_service_profile(category)
    return str(profile["price_unit"]) if profile else ""


def service_context(category: str | None) -> dict:
    """给 LLM 提示词与 Mock 生成器使用的服务上下文快照。"""
    profile = get_service_profile(category)
    if profile is None:
        return {}
    return {
        "is_service": True,
        "category": profile["category"],
        "short_name": profile["short_name"],
        "business_name": profile["business_name"],
        "price_unit": profile["price_unit"],
        "persona": profile["persona"],
        "needs": list(profile["needs"]),
        "scenarios": list(profile["scenarios"]),
        "packages": [dict(item) for item in profile["packages"]],
        "trust_points": list(profile["trust_points"]),
        "ctas": list(profile["ctas"]),
        "visual_template": profile["visual_template"],
        "forbidden_claims": list(profile["forbidden_claims"]),
        "claim_guidance": profile["claim_guidance"],
        "keywords": list(profile["keywords"]),
        "hero_copy": profile["hero_copy"],
    }
