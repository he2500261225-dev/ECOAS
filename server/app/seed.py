"""演示种子数据：两家店铺、五个处于不同闭环阶段的单品。

P1 防晒衣   —— 演示起点：已建档、已录竞品，等待现场生成诊断
P2 无线充   —— 完整闭环历史：诊断 -> 创意 -> 素材 -> 投放 -> 数据 -> 复盘
P3 冰感袖套 —— 已诊断
P4 榨汁杯   —— 创意就绪，库存告警
P5 降噪耳机 —— 投放复盘中，库存告警
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ASSET_DIR
from .db import Base, SessionLocal, engine
from .models import (
    ApprovalLog,
    Asset,
    Competitor,
    CreativePlan,
    Diagnosis,
    ImageScheme,
    MetricRecord,
    PlatformSkuMapping,
    Placement,
    Product,
    ReviewReport,
    Sku,
    StockFlow,
    Store,
    SystemConfig,
    User,
    VideoScript,
    VideoShot,
)
from .security import hash_password
from .services import llm
from .services.service_profiles import service_context


def _svg(filename: str, title: str, subtitle: str, c1: str, c2: str, badge: str) -> str:
    content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 900 900">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="900" height="900" fill="url(#g)"/>
  <circle cx="700" cy="200" r="260" fill="#ffffff" opacity="0.10"/>
  <circle cx="180" cy="760" r="220" fill="#ffffff" opacity="0.08"/>
  <text x="70" y="120" fill="#ffffff" opacity="0.85" font-size="30" font-family="sans-serif">{badge}</text>
  <text x="70" y="560" fill="#ffffff" font-size="64" font-weight="bold" font-family="sans-serif">{title}</text>
  <text x="70" y="630" fill="#ffffff" opacity="0.88" font-size="34" font-family="sans-serif">{subtitle}</text>
  <rect x="70" y="700" width="360" height="84" rx="42" fill="#ffffff"/>
  <text x="250" y="754" fill="{c1}" font-size="32" font-weight="bold" text-anchor="middle" font-family="sans-serif">立即抢购</text>
</svg>"""
    path = ASSET_DIR / filename
    path.write_text(content, encoding="utf-8")
    return f"/files/assets/{filename}"


def _diagnosis_content_wireless() -> dict:
    return {
        "audience": {
            "persona": "25-35 岁数码爱好者与通勤白领，手机重度使用、桌面与床头充电场景明确",
            "needs": ["快充不伤电池", "边充边用不烫手", "桌面整洁少线材"],
            "scenarios": ["办公室桌面", "床头夜充", "差旅随身"],
        },
        "price_analysis": {
            "position": "79-99 元处于磁吸无线充中端价格带",
            "competitor_range": "新入场竞品下探至 59 元，品牌竞品上探至 129 元",
            "suggestion": "维持 89 元主价，强化温控与 15W 快充的差异化，不建议正面跟价",
        },
        "selling_points": [
            {"point": "智能温控不烫手", "evidence": "双层石墨烯散热 + 温度保护芯片", "diff": "低价竞品无温控描述，实测表面温度高 8-10℃"},
            {"point": "15W 磁吸快充", "evidence": "磁吸对位，充电效率较普通无线充提升 40%", "diff": "同价位多为 10W"},
            {"point": "轻薄便携", "evidence": "厚度 8mm、重量 62g", "diff": "品牌竞品厚重，不便差旅"},
        ],
        "conversion_blockers": [
            "主图未直观呈现温控能力，用户难以感知差异",
            "详情页缺少边充边玩实测温度曲线",
            "低价竞品以 59 元抢占搜索首屏，价格锚点被拉低",
        ],
        "optimization_directions": [
            "主图强化温控可视化表达（温度计/对比数据）",
            "增加实测视频素材，突出边充边玩场景",
            "以 89 元 + 赠品形式守住价格带，而非直接降价",
        ],
    }


def _diagnosis_content_sleeve() -> dict:
    return {
        "audience": {
            "persona": "18-30 岁骑行、通勤与户外徒步人群，注重防晒与清凉感",
            "needs": ["UPF50+ 防晒", "冰感亲肤", "防滑不卷边"],
            "scenarios": ["骑行通勤", "夏日徒步", "开车防晒"],
        },
        "price_analysis": {
            "position": "29-59 元处于袖套低价格带，具备走量潜力",
            "competitor_range": "头部品牌 59-79 元，白牌 9.9-19.9 元",
            "suggestion": "以 39 元两支装切入，强调冰感面料与防晒检测报告",
        },
        "selling_points": [
            {"point": "冰感凉皮面料", "evidence": "接触瞬间降温 1.8℃", "diff": "白牌多为普通涤纶"},
            {"point": "UPF50+ 检测认证", "evidence": "附第三方检测报告", "diff": "低价竞品少有认证"},
            {"point": "硅胶防滑条", "evidence": "骑行 2 小时不卷边", "diff": "同价位多为无防滑设计"},
        ],
        "conversion_blockers": [
            "袖套类目同质化严重，主图难以体现冰感差异",
            "详情页缺少上臂围尺码建议，退货咨询多",
        ],
        "optimization_directions": [
            "主图增加冰感温度计对比元素",
            "详情页补充尺码对照与骑行实测场景",
        ],
    }


def _add_plan(db: Session, product: Product, diagnosis: Diagnosis | None, schemes: list[dict], scripts: list[dict]) -> CreativePlan:
    plan = CreativePlan(
        product_id=product.id,
        diagnosis_id=diagnosis.id if diagnosis else None,
        version=1,
        status="confirmed",
    )
    db.add(plan)
    db.flush()
    for i, s in enumerate(schemes, start=1):
        db.add(
            ImageScheme(
                plan_id=plan.id,
                order_no=i,
                title=s["title"],
                layout=s["layout"],
                copy=s["copy"],
                main_selling_point=s["point"],
                visual_tip=s["visual"],
                status=s.get("status", "draft"),
            )
        )
    for i, s in enumerate(scripts, start=1):
        script = VideoScript(
            plan_id=plan.id,
            order_no=i,
            title=s["title"],
            hook_3s=s["hook"],
            closing_cta=s["cta"],
            status=s.get("status", "draft"),
        )
        db.add(script)
        db.flush()
        for j, shot in enumerate(s["shots"], start=1):
            db.add(
                VideoShot(
                    script_id=script.id,
                    shot_no=j,
                    duration_sec=shot[0],
                    scene_desc=shot[1],
                    voiceover=shot[2],
                    cta_line=shot[3],
                )
            )
    return plan


def _wireless_schemes() -> list[dict]:
    return [
        {
            "title": "方向一：温控安全感",
            "layout": "产品居中悬浮，背景为深色桌面，右侧叠加温度计仪表盘与「38℃ 恒温」数据标签，左上角放充电中手机轮廓。",
            "copy": "边充边玩，也不烫手",
            "point": "智能温控芯片 + 双层石墨烯散热",
            "visual": "深空灰科技感配色，冷光蓝点缀，温度数字使用高对比白色，突出「控温」而非「功率」。",
            "status": "confirmed",
        },
        {
            "title": "方向二：桌面场景全家福",
            "layout": "45° 俯拍办公桌面，无线充、手机、耳机、咖啡杯形成生活化构图，产品位于视觉中心，右下角放「15W」角标。",
            "copy": "桌面只留一根线",
            "point": "磁吸对位 + 轻薄便携",
            "visual": "暖白木质桌面，自然光，营造整洁通勤场景，适合种草型点击。",
        },
        {
            "title": "方向三：参数对比硬核",
            "layout": "左右分屏对比：左侧本品 15W / 8mm / 温控芯片，右侧同价位竞品 10W / 厚重 / 无温控，中间用对勾与叉号强化差异。",
            "copy": "同样 89 元，为什么要买 10W？",
            "point": "15W 快充与温控双差异",
            "visual": "高饱和红蓝对比，信息密度高，适合搜索广告位与比价人群。",
        },
    ]


def _wireless_scripts() -> list[dict]:
    return [
        {
            "title": "脚本一：通勤桌面实测",
            "hook": "手机往桌上一放，30 秒后电量肉眼可见地涨？",
            "cta": "点左下角，今天下单送 20W 快充头",
            "shots": [
                (3, "特写：手机随意放上无线充，磁吸「咔哒」对位", "每天下班回家，我最烦的就是找线", "磁吸一放即充"),
                (5, "中景：桌面全景，手机横屏播放视频，无线充指示灯常亮", "边充边刷剧，最怕的就是发烫", "15W 快充实测"),
                (6, "特写：测温枪对准充电面板，屏幕显示 38.2℃", "实测表面温度 38 度，比体温高一点点", "温控芯片实时守护"),
                (4, "特写：手掌覆盖面板 10 秒后抬起", "摸上去只是温温的，完全不烫手", "边充边玩也安心"),
            ],
        },
        {
            "title": "脚本二：温控拆解硬核向",
            "hook": "59 块的无线充和 89 块的，差在哪？",
            "cta": "评论区扣「温控」，给你看完整实测数据",
            "shots": [
                (3, "对比镜头：两款无线充并排，温度计分别贴上", "同样充 30 分钟，温度差了整整 9 度", "低价不等于低质？"),
                (6, "拆解镜头：展示石墨烯散热片与温控芯片", "秘密就在这两层石墨烯和一颗温控芯片", "双层散热结构"),
                (5, "实拍：手机边玩游戏边充电，帧率稳定", "边玩边充不掉帧，电池也不发烫", "游戏党福音"),
                (4, "口播特写：手持产品对准镜头", "多花 30 块，买的是电池寿命", "现在下单立减 10 元"),
            ],
        },
        {
            "title": "脚本三：差旅轻装场景",
            "hook": "出差只带一个充电器，够吗？",
            "cta": "点击购物车，出差套装立省 30",
            "shots": [
                (3, "俯拍：行李箱内，无线充放进收纳袋", "出差我最怕带一堆线", "一个就够"),
                (5, "场景：酒店床头，手机放上即充", "到酒店往床头一放，第二天满电", "磁吸即充"),
                (5, "特写：产品厚度与银行卡对比", "8 毫米厚，比银行卡还薄", "轻薄便携"),
                (4, "口播：手持产品与手机同框", "89 元，把桌面和差旅都收拾干净", "点击下方链接"),
            ],
        },
    ]


def _juicer_schemes() -> list[dict]:
    return [
        {
            "title": "方向一：30 秒鲜榨场景",
            "layout": "明亮厨房台面，榨汁杯居中，周围摆放橙子、草莓与冰块，右上角叠加「30s」大字。",
            "copy": "起床到出门，一杯鲜榨刚好",
            "point": "30 秒快榨 + 一键清洗",
            "visual": "高饱和橙绿配色，晨光氛围，突出速度与新鲜感。",
            "status": "confirmed",
        },
        {
            "title": "方向二：便携随行",
            "layout": "人物手持榨汁杯走在街上，杯身与手提包同框，背景虚化，右下角放容量标识。",
            "copy": "榨完直接带走，路上喝",
            "point": "400ml 便携杯身 + 无线续航",
            "visual": "生活方式摄影风格，低饱和奶油色，贴近通勤女性。",
        },
        {
            "title": "方向三：清洗痛点对比",
            "layout": "左右对比：传统榨汁机拆洗零件 vs 本品一键自清洁，中间用水流箭头连接。",
            "copy": "洗杯子只要 10 秒",
            "point": "一键自清洁，不藏果渣",
            "visual": "蓝白清爽配色，强调水流与洁净感，适合详情页首屏。",
        },
    ]


def _juicer_scripts() -> list[dict]:
    return [
        {
            "title": "脚本一：打工人早餐",
            "hook": "早上多睡 10 分钟，还能喝上鲜榨？",
            "cta": "点购物车，今天下单送食谱卡",
            "shots": [
                (3, "特写：闹钟响，主角按掉后翻身", "早八人真的没时间做早餐", "多睡 10 分钟"),
                (5, "中景：水果切块丢进杯子，按下开关", "水果丢进去，30 秒搞定", "一键快榨"),
                (5, "特写：杯盖拧下直接带走", "杯子就是随行杯，出门直接拿", "榨完即走"),
                (4, "口播：主角在地铁上喝果汁", "一杯鲜榨，开启一天", "点击下方链接"),
            ],
        },
        {
            "title": "脚本二：带娃家庭",
            "hook": "孩子不爱吃水果？换个方式试试",
            "cta": "拍两件更划算，全家一人一杯",
            "shots": [
                (3, "场景：孩子推开果盘", "水果切好端过去，孩子看都不看", "换个思路"),
                (6, "中景：亲子一起把水果放进榨汁杯", "让他自己动手，榨成一杯果汁", "亲子 DIY"),
                (5, "特写：孩子举起杯子喝光", "自己做的，喝得干干净净", "无渣口感"),
                (4, "口播：妈妈展示清洗过程", "冲一下就好洗，不藏果渣", "一键自清洁"),
            ],
        },
        {
            "title": "脚本三：露营便携",
            "hook": "露营带榨汁机？这次是真的",
            "cta": "露营季套装立减 40，点击抢购",
            "shots": [
                (3, "全景：露营地桌面上摆着榨汁杯", "朋友都问我，露营怎么还带榨汁机", "无线便携"),
                (6, "特写：无电源环境下榨汁，杯体运转", "无线续航，榨 8 杯没问题", "4000mAh 电池"),
                (5, "场景：倒进玻璃杯，加冰块", "西瓜汁加冰，夏天的快乐", "一键清洗"),
                (4, "口播：举杯与朋友碰杯", "露营幸福感，就藏在这一杯里", "点击购物车"),
            ],
        },
    ]


def _seed_assets(db: Session, product: Product, manager_id: int, operator_id: int) -> None:
    if product.name.startswith("磁吸无线充"):
        items = [
            ("wireless_a.svg", "边充边玩 也不烫手", "15W 磁吸快充 · 智能温控", "#1f2937", "#0f766e", "主图方案 A", "image", "image_scheme", 1),
            ("wireless_b.svg", "桌面只留一根线", "磁吸对位 · 轻薄便携", "#334155", "#1d4ed8", "主图方案 B", "image", "image_scheme", 2),
            ("wireless_video.svg", "温控实测 38℃", "模拟视频素材 · 分镜动效预览", "#111827", "#7c3aed", "视频素材", "video", "video_script", 1),
        ]
    elif product.name.startswith("主动降噪"):
        items = [
            ("earbuds_a.svg", "通勤降噪 一戴入静", "42dB 主动降噪 · 38 小时续航", "#0f172a", "#0369a1", "主图方案 A", "image", "image_scheme", 1),
            ("earbuds_b.svg", "地铁里的私人音乐厅", "自适应降噪 · 通透模式", "#1e1b4b", "#6d28d9", "主图方案 B", "image", "image_scheme", 2),
        ]
    else:
        return

    for idx, (filename, title, subtitle, c1, c2, badge, atype, stype, sid) in enumerate(items, start=1):
        path = _svg(filename, title, subtitle, c1, c2, badge)
        db.add(
            Asset(
                product_id=product.id,
                task_id=None,
                type=atype,
                source_type=stype,
                source_id=sid,
                filename=filename,
                file_path=path,
                mime="image/svg+xml",
                version=1,
                status="approved",
                tags_json=["演示素材", "已审核"] if idx == 1 else ["演示素材"],
                review_note="素材清晰、卖点表达准确，可投入使用。",
                reviewed_by=manager_id if idx == 1 else operator_id,
                reviewed_at=datetime.utcnow() - timedelta(days=3),
            )
        )


def seed(db: Session | None = None) -> None:
    own = db is None
    db = db or SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            seed_service_business(db)
            return

        today = date.today()
        operator = User(
            username="operator",
            password_hash=hash_password("123456"),
            display_name="张琳",
            role="operator",
        )
        manager = User(
            username="manager",
            password_hash=hash_password("123456"),
            display_name="李瓒",
            role="manager",
        )
        db.add_all([operator, manager])
        db.flush()

        store_tmall = Store(name="天猫旗舰店", platform="taobao", auth_status="authorized", auth_ref="oauth_****9f2a")
        store_douyin = Store(name="抖音小店", platform="douyin", auth_status="authorized", auth_ref="oauth_****3c71")
        store_jd = Store(name="京东自营店", platform="jd", auth_status="expired", auth_ref="oauth_****7bd0")
        db.add_all([store_tmall, store_douyin, store_jd])
        db.flush()

        # ---------- P1 防晒衣：演示起点 ----------
        p1 = Product(
            store_id=store_tmall.id,
            name="冰丝防晒衣 UPF50+ 夏季户外",
            category="防晒服饰",
            price_min=129,
            price_max=199,
            description="原纱型冰丝面料，UPF50+ 防晒，凉感透气，适合通勤与轻户外场景。",
        )
        db.add(p1)
        db.flush()
        p1_skus = [
            Sku(product_id=p1.id, spec_json={"颜色": "雾霾蓝", "尺码": "M"}, price=149, stock=120, warn_threshold=20),
            Sku(product_id=p1.id, spec_json={"颜色": "雾霾蓝", "尺码": "L"}, price=149, stock=86, warn_threshold=20),
            Sku(product_id=p1.id, spec_json={"颜色": "月光白", "尺码": "M"}, price=159, stock=54, warn_threshold=20),
        ]
        db.add_all(p1_skus)
        db.flush()
        p1.main_sku_id = p1_skus[0].id
        for sku in p1_skus:
            db.add(
                PlatformSkuMapping(
                    sku_id=sku.id,
                    platform="taobao",
                    platform_spec_name=f"{sku.spec_json['颜色']}/{sku.spec_json['尺码']}",
                    platform_price=sku.price,
                    platform_sku_code=f"TM{p1.id}{sku.id:04d}",
                )
            )
        db.add_all(
            [
                Competitor(
                    product_id=p1.id,
                    platform="taobao",
                    name="蕉下 冰丝防晒衣 女",
                    price=189,
                    url="https://example.com/item/jiaoxia",
                    params_json={"UPF": "50+", "面料": "原纱型冰丝", "克重": "85g", "透气性": "中等"},
                    sales_volume=20000,
                    rating=4.8,
                    source="manual",
                    parse_status="confirmed",
                ),
                Competitor(
                    product_id=p1.id,
                    platform="douyin",
                    name="觅橘 轻户外防晒衣",
                    price=99,
                    url="https://example.com/item/miju",
                    params_json={"UPF": "40+", "面料": "涂层型", "克重": "110g", "透气性": "较弱"},
                    sales_volume=8000,
                    rating=4.6,
                    source="ai_parse",
                    parse_status="confirmed",
                ),
            ]
        )

        # ---------- P2 无线充：完整闭环 ----------
        p2 = Product(
            store_id=store_douyin.id,
            name="磁吸无线充电器 15W 快充",
            category="数码配件",
            price_min=79,
            price_max=99,
            description="15W 磁吸无线快充，双层石墨烯散热，边充边玩不发烫，适配主流磁吸机型。",
        )
        db.add(p2)
        db.flush()
        p2_skus = [
            Sku(product_id=p2.id, spec_json={"颜色": "曜石黑"}, price=89, stock=210, warn_threshold=30),
            Sku(product_id=p2.id, spec_json={"颜色": "珍珠白"}, price=89, stock=300, warn_threshold=30),
        ]
        db.add_all(p2_skus)
        db.flush()
        p2.main_sku_id = p2_skus[0].id
        for sku in p2_skus:
            db.add(
                PlatformSkuMapping(
                    sku_id=sku.id,
                    platform="douyin",
                    platform_spec_name=f"{sku.spec_json['颜色']} 标准版",
                    platform_price=sku.price,
                    platform_sku_code=f"DY{p2.id}{sku.id:04d}",
                )
            )
        db.add(
            Competitor(
                product_id=p2.id,
                platform="douyin",
                name="闪极 磁吸无线充 10W",
                price=59,
                url="https://example.com/item/shanyi",
                params_json={"功率": "10W", "厚度": "11mm", "温控": "无", "材质": "ABS"},
                sales_volume=12000,
                rating=4.5,
                source="manual",
                parse_status="confirmed",
            )
        )

        d2 = Diagnosis(
            product_id=p2.id,
            version=1,
            status="current",
            content_json=_diagnosis_content_wireless(),
            model="mock-diagnosis-v1",
            created_by=operator.id,
        )
        db.add(d2)
        db.flush()
        plan2 = _add_plan(db, p2, d2, _wireless_schemes(), _wireless_scripts())
        db.flush()

        placement2 = Placement(
            product_id=p2.id,
            creative_plan_id=plan2.id,
            audience_json={
                "name": "数码通勤人群包",
                "description": "近 30 天浏览过磁吸无线充、手机配件类目，25-35 岁一二线城市",
                "estimated_reach": 180000,
            },
            bid_json={"strategy": "目标 ROI 出价", "target_roi": 3.2, "bid_range": "0.8-1.2 元"},
            budget=8000,
            period_start=(today - timedelta(days=25)).isoformat(),
            period_end=(today - timedelta(days=19)).isoformat(),
            ab_json=[
                {"group": "A", "assets": ["主图方案 A", "脚本一"], "budget_ratio": 0.5},
                {"group": "B", "assets": ["主图方案 B", "脚本二"], "budget_ratio": 0.5},
            ],
            risk_level="high",
            status="closed",
            targets_json={"gmv": 30000, "roi": 3.2, "ctr": 0.045, "cvr": 0.032},
            note="小预算验证温控卖点与桌面场景的点击差异。",
            created_by=operator.id,
            approved_by=manager.id,
            approved_at=datetime.utcnow() - timedelta(days=26),
        )
        db.add(placement2)
        db.flush()
        db.add_all(
            [
                ApprovalLog(
                    placement_id=placement2.id,
                    action="submit",
                    actor_id=operator.id,
                    actor_name=operator.display_name,
                    role=operator.role,
                    note="提交审批，预算 8000 元，高风险实验。",
                    created_at=datetime.utcnow() - timedelta(days=27),
                ),
                ApprovalLog(
                    placement_id=placement2.id,
                    action="approve",
                    actor_id=manager.id,
                    actor_name=manager.display_name,
                    role=manager.role,
                    note="同意小预算测款，注意监控温控卖点点击率。",
                    created_at=datetime.utcnow() - timedelta(days=26),
                ),
            ]
        )
        _seed_assets(db, p2, manager.id, operator.id)

        p2_daily = [
            (20100, 986, 31, 3580, 1120),
            (21800, 1072, 34, 3920, 1180),
            (23600, 1150, 36, 4150, 1240),
            (22400, 1108, 33, 3840, 1160),
            (25200, 1240, 38, 4420, 1310),
            (24100, 1188, 35, 4080, 1250),
            (26300, 1298, 39, 4560, 1360),
        ]
        metric_actual = {"impressions": 0, "clicks": 0, "orders": 0, "gmv": 0.0, "spend": 0.0}
        for i, (imp, clicks, orders, gmv, spend) in enumerate(p2_daily):
            d = today - timedelta(days=25 - i)
            db.add(
                MetricRecord(
                    product_id=p2.id,
                    placement_id=placement2.id,
                    date=d.isoformat(),
                    impressions=imp,
                    clicks=clicks,
                    orders=orders,
                    gmv=gmv,
                    spend=spend,
                    source="manual",
                    created_by=operator.id,
                )
            )
            metric_actual["impressions"] += imp
            metric_actual["clicks"] += clicks
            metric_actual["orders"] += orders
            metric_actual["gmv"] += gmv
            metric_actual["spend"] += spend

        ctr = metric_actual["clicks"] / metric_actual["impressions"]
        cvr = metric_actual["orders"] / metric_actual["clicks"]
        roi = metric_actual["gmv"] / metric_actual["spend"]
        report_md = f"""# 磁吸无线充电器 15W 快充 · 经营复盘报告

**复盘周期**：{(today - timedelta(days=25)).isoformat()} ~ {(today - timedelta(days=19)).isoformat()}
**投放计划**：数码通勤人群包 / 目标 ROI 出价 / 预算 ¥8000（高风险实验，已由李瓒审批）

## 一、核心指标对比

| 指标 | 目标 | 实际 | 达成 |
| --- | --- | --- | --- |
| GMV | ¥{30000:,} | ¥{metric_actual['gmv']:,.0f} | {'未达成' if metric_actual['gmv'] < 30000 else '达成'} |
| ROI | 3.20 | {roi:.2f} | {'达成' if roi >= 3.2 else '未达成'} |
| CTR | 4.50% | {ctr * 100:.2f}% | {'达成' if ctr >= 0.045 else '未达成'} |
| CVR | 3.20% | {cvr * 100:.2f}% | {'未达成' if cvr < 0.032 else '达成'} |

## 二、流量与转化归因

- **CTR 超预期**：温控安全感主图（方案 A）在搜索广告位点击率显著高于桌面场景图，用户对「不烫手」卖点敏感。
- **CVR 略低于目标**：详情页缺少边充边玩温度实测曲线，用户进入详情页后对温控真实性存疑，跳失集中在参数区。
- **ROI 基本达标**：客单价稳定在 89 元，花费控制在预算内，主要缺口来自转化率而非流量成本。

## 三、后续迭代行动建议

1. 在详情页首屏加入 30 分钟温度实测曲线与边充边玩视频片段，降低验证成本。
2. 下一轮创意保留「温控安全感」方向，新增「边充边玩 30 分钟温度对比」主图方向。
3. 将人群包扩展至「手游玩家」兴趣标签，小预算 A/B 测试其转化差异。
4. 维持 89 元价格，不跟随 59 元竞品降价，以赠品与温控差异守住价格带。
"""
        db.add(
            ReviewReport(
                product_id=p2.id,
                placement_id=placement2.id,
                markdown=report_md,
                structured_json={
                    "period": {
                        "start": (today - timedelta(days=25)).isoformat(),
                        "end": (today - timedelta(days=19)).isoformat(),
                    },
                    "metric_comparison": [
                        {"metric": "GMV", "target": 30000, "actual": round(metric_actual["gmv"], 2), "unit": "元"},
                        {"metric": "ROI", "target": 3.2, "actual": round(roi, 2), "unit": ""},
                        {"metric": "CTR", "target": 0.045, "actual": round(ctr, 4), "unit": ""},
                        {"metric": "CVR", "target": 0.032, "actual": round(cvr, 4), "unit": ""},
                    ],
                    "attribution": "CTR 超预期，CVR 略低于目标，ROI 基本达标；主要缺口在详情页转化而非流量成本。",
                    "action_items": [
                        "详情页首屏加入 30 分钟温度实测曲线与边充边玩视频片段",
                        "保留「温控安全感」方向，新增温度对比主图方向",
                        "人群包扩展至「手游玩家」兴趣标签做小预算 A/B 测试",
                        "维持 89 元价格带，以赠品与温控差异应对低价竞品",
                    ],
                },
                status="final",
                created_by=operator.id,
            )
        )

        # ---------- P3 冰感袖套：已诊断 ----------
        p3 = Product(
            store_id=store_tmall.id,
            name="冰感防晒袖套 骑行防滑款",
            category="防晒服饰",
            price_min=29,
            price_max=59,
            description="冰感凉皮面料，UPF50+，硅胶防滑不卷边，骑行通勤两用。",
        )
        db.add(p3)
        db.flush()
        p3_skus = [
            Sku(product_id=p3.id, spec_json={"颜色": "黑色", "规格": "两只装"}, price=39, stock=150, warn_threshold=30),
            Sku(product_id=p3.id, spec_json={"颜色": "灰色", "规格": "两只装"}, price=39, stock=90, warn_threshold=30),
        ]
        db.add_all(p3_skus)
        db.flush()
        p3.main_sku_id = p3_skus[0].id
        db.add(
            Competitor(
                product_id=p3.id,
                platform="taobao",
                name="蕉下 冰丝袖套",
                price=59,
                url="https://example.com/item/sleeve",
                params_json={"UPF": "50+", "面料": "冰丝", "防滑": "有"},
                sales_volume=15000,
                rating=4.7,
                source="manual",
                parse_status="confirmed",
            )
        )
        db.add(
            Diagnosis(
                product_id=p3.id,
                version=1,
                status="current",
                content_json=_diagnosis_content_sleeve(),
                model="mock-diagnosis-v1",
                created_by=operator.id,
            )
        )

        # ---------- P4 榨汁杯：创意就绪、库存告警 ----------
        p4 = Product(
            store_id=store_douyin.id,
            name="便携榨汁杯 无线充电款",
            category="厨房小电",
            price_min=89,
            price_max=129,
            description="400ml 便携杯身，30 秒快榨，一键自清洁，无线续航 8 杯。",
        )
        db.add(p4)
        db.flush()
        p4_skus = [
            Sku(product_id=p4.id, spec_json={"颜色": "奶油白"}, price=99, stock=4, warn_threshold=15),
            Sku(product_id=p4.id, spec_json={"颜色": "薄荷绿"}, price=99, stock=40, warn_threshold=15),
        ]
        db.add_all(p4_skus)
        db.flush()
        p4.main_sku_id = p4_skus[0].id
        db.add(
            StockFlow(
                sku_id=p4_skus[0].id,
                change=-26,
                reason="sale",
                stock_after=4,
                operator_id=operator.id,
                created_at=datetime.utcnow() - timedelta(days=1),
            )
        )
        d4 = Diagnosis(
            product_id=p4.id,
            version=1,
            status="current",
            content_json={
                "audience": {
                    "persona": "22-35 岁注重健康饮食的都市女性与带娃家庭",
                    "needs": ["便携", "好清洗", "出汁细腻"],
                    "scenarios": ["早餐", "办公", "露营"],
                },
                "price_analysis": {
                    "position": "89-129 元处于便携榨汁杯中端价格带",
                    "competitor_range": "白牌 49-69 元，品牌 149-199 元",
                    "suggestion": "以 99 元主价 + 食谱赠品强化价值感",
                },
                "selling_points": [
                    {"point": "30 秒快榨", "evidence": "六叶刀头 + 4000mAh 电池", "diff": "同价位多为四叶刀头"},
                    {"point": "一键自清洁", "evidence": "加水一键搅洗", "diff": "多数竞品需拆洗"},
                    {"point": "无线便携", "evidence": "满电可榨 8 杯", "diff": "白牌续航约 4 杯"},
                ],
                "conversion_blockers": ["用户担心清洗麻烦", "对续航能力存疑"],
                "optimization_directions": ["主图强化自清洁演示", "短视频加入续航实测"],
            },
            model="mock-diagnosis-v1",
            created_by=operator.id,
        )
        db.add(d4)
        db.flush()
        _add_plan(db, p4, d4, _juicer_schemes(), _juicer_scripts())

        # ---------- P5 降噪耳机：复盘中、库存告警 ----------
        p5 = Product(
            store_id=store_tmall.id,
            name="主动降噪蓝牙耳机 Pro",
            category="数码配件",
            price_min=299,
            price_max=399,
            description="42dB 主动降噪，38 小时续航，自适应通透模式。",
        )
        db.add(p5)
        db.flush()
        p5_skus = [
            Sku(product_id=p5.id, spec_json={"颜色": "曜石黑"}, price=329, stock=6, warn_threshold=20),
            Sku(product_id=p5.id, spec_json={"颜色": "云雾白"}, price=329, stock=80, warn_threshold=20),
        ]
        db.add_all(p5_skus)
        db.flush()
        p5.main_sku_id = p5_skus[0].id
        placement5 = Placement(
            product_id=p5.id,
            creative_plan_id=None,
            audience_json={
                "name": "通勤降噪人群包",
                "description": "近 30 天搜索降噪耳机、通勤配饰，18-35 岁一二线城市",
                "estimated_reach": 420000,
            },
            bid_json={"strategy": "目标 ROI 出价", "target_roi": 2.8, "bid_range": "1.5-2.2 元"},
            budget=12000,
            period_start=(today - timedelta(days=13)).isoformat(),
            period_end=(today + timedelta(days=7)).isoformat(),
            ab_json=[
                {"group": "A", "assets": ["主图方案 A", "脚本一"], "budget_ratio": 0.6},
                {"group": "B", "assets": ["主图方案 B", "脚本二"], "budget_ratio": 0.4},
            ],
            risk_level="high",
            status="approved",
            targets_json={"gmv": 120000, "roi": 2.8, "ctr": 0.04, "cvr": 0.055},
            note="大促前蓄水，预算 12000 元，需主管审批。",
            created_by=operator.id,
            approved_by=manager.id,
            approved_at=datetime.utcnow() - timedelta(days=14),
        )
        db.add(placement5)
        db.flush()
        db.add_all(
            [
                ApprovalLog(
                    placement_id=placement5.id,
                    action="submit",
                    actor_id=operator.id,
                    actor_name=operator.display_name,
                    role=operator.role,
                    note="提交大促前蓄水投放实验。",
                    created_at=datetime.utcnow() - timedelta(days=15),
                ),
                ApprovalLog(
                    placement_id=placement5.id,
                    action="approve",
                    actor_id=manager.id,
                    actor_name=manager.display_name,
                    role=manager.role,
                    note="同意，按周监控 ROI。",
                    created_at=datetime.utcnow() - timedelta(days=14),
                ),
            ]
        )
        _seed_assets(db, p5, manager.id, operator.id)

        for i in range(14):
            d = today - timedelta(days=13 - i)
            impressions = 12000 + (i * 137) % 4000
            clicks = int(impressions * (0.043 + (i % 5) * 0.001))
            orders = int(clicks * (0.025 + (i % 4) * 0.001))
            db.add(
                MetricRecord(
                    product_id=p5.id,
                    placement_id=placement5.id,
                    date=d.isoformat(),
                    impressions=impressions,
                    clicks=clicks,
                    orders=orders,
                    gmv=orders * 329,
                    spend=1180 + i * 12,
                    source="import" if i < 7 else "manual",
                    created_by=operator.id,
                )
            )

        # ---------- 系统配置默认值 ----------
        defaults = {
            "llm": {
                "mode": "mock",
                "provider": "anthropic",
                "base_url": "",
                "api_key": "",
                "model": "claude-sonnet-5-5",
                "temperature": 0.7,
                "timeout_seconds": 60,
            },
            "media": {
                "image_timeout": 300,
                "video_timeout": 600,
                "delay_min": 3,
                "delay_max": 6,
                "fail_rate": 0.15,
            },
            "queue": {"concurrency": 2, "max_retry": 2, "heartbeat_seconds": 5, "sweep_seconds": 5},
            "risk": {"high_risk_budget": 5000},
            "platform_auth": {"taobao": "authorized", "douyin": "authorized", "jd": "expired"},
        }
        for key, value in defaults.items():
            db.add(SystemConfig(key=key, value_json=value, updated_by=manager.id))

        db.commit()
        seed_service_business(db)
    finally:
        if own:
            db.close()


def _ensure_local_store(db: Session, name: str, auth_ref: str) -> Store:
    store = db.scalar(select(Store).where(Store.name == name))
    if store is not None:
        return store
    store = Store(
        name=name,
        platform="local",
        auth_status="authorized",
        auth_ref=auth_ref,
    )
    db.add(store)
    db.flush()
    return store


def _ensure_service_product(
    db: Session,
    store: Store,
    name: str,
    category: str,
    price_min: float,
    price_max: float,
    description: str,
) -> tuple[Product, bool]:
    product = db.scalar(select(Product).where(Product.name == name))
    if product is not None:
        return product, False
    product = Product(
        store_id=store.id,
        name=name,
        category=category,
        price_min=price_min,
        price_max=price_max,
        description=description,
    )
    db.add(product)
    db.flush()
    return product, True


def _ensure_service_skus(db: Session, product: Product, packages: list[tuple[dict, float]]) -> None:
    existing = db.scalar(select(Sku).where(Sku.product_id == product.id).limit(1))
    if existing is not None:
        return
    first_sku: Sku | None = None
    for spec, price in packages:
        sku = Sku(
            product_id=product.id,
            spec_json=spec,
            price=float(price),
            stock=9999,
            warn_threshold=0,
        )
        db.add(sku)
        db.flush()
        if first_sku is None:
            first_sku = sku
        spec_name = " / ".join(str(value) for value in spec.values())
        db.add(
            PlatformSkuMapping(
                sku_id=sku.id,
                platform="local",
                platform_spec_name=spec_name,
                platform_price=float(price),
                platform_sku_code=f"LOCAL{product.id}{sku.id:04d}",
            )
        )
    if first_sku is not None and product.main_sku_id is None:
        product.main_sku_id = first_sku.id


def _ensure_competitors(db: Session, product: Product, items: list[dict]) -> None:
    existing = db.scalar(select(Competitor).where(Competitor.product_id == product.id).limit(1))
    if existing is not None:
        return
    for item in items:
        db.add(
            Competitor(
                product_id=product.id,
                platform="local",
                name=item["name"],
                price=float(item["price"]),
                url=item.get("url", ""),
                params_json=item.get("params_json", {}),
                sales_volume=int(item.get("sales_volume", 0)),
                rating=float(item.get("rating", 0)),
                source="manual",
                parse_status="confirmed",
            )
        )
    db.flush()


def _service_context(db: Session, product: Product) -> dict:
    skus = db.scalars(select(Sku).where(Sku.product_id == product.id).order_by(Sku.id)).all()
    competitors = db.scalars(
        select(Competitor).where(Competitor.product_id == product.id).order_by(Competitor.id)
    ).all()
    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "price_min": product.price_min,
            "price_max": product.price_max,
            "description": product.description,
        },
        "skus": [
            {
                "id": sku.id,
                "spec_json": sku.spec_json,
                "price": sku.price,
                "stock": sku.stock,
                "warn_threshold": sku.warn_threshold,
            }
            for sku in skus
        ],
        "competitors": [
            {
                "id": item.id,
                "name": item.name,
                "platform": item.platform,
                "price": item.price,
                "params_json": item.params_json or {},
                "sales_volume": item.sales_volume,
                "rating": item.rating,
            }
            for item in competitors
        ],
        "service_profile": service_context(product.category),
        "action_items": [],
    }


def _ensure_service_diagnosis(db: Session, product: Product, created_by: int) -> Diagnosis | None:
    current = db.scalar(
        select(Diagnosis).where(
            Diagnosis.product_id == product.id, Diagnosis.status == "current"
        )
    )
    if current is not None:
        return current
    context = _service_context(db, product)
    content = llm.mock_content("diagnosis", context)
    diagnosis = Diagnosis(
        product_id=product.id,
        version=1,
        status="current",
        content_json=content,
        model="mock-diagnosis-v1",
        created_by=created_by,
    )
    db.add(diagnosis)
    db.flush()
    return diagnosis


def _ensure_service_plan(
    db: Session, product: Product, diagnosis: Diagnosis | None
) -> CreativePlan | None:
    existing = db.scalar(select(CreativePlan).where(CreativePlan.product_id == product.id).limit(1))
    if existing is not None:
        return existing
    if diagnosis is None:
        return None

    context = _service_context(db, product)
    context["diagnosis"] = diagnosis.content_json or {}
    context["diagnosis_version"] = diagnosis.version
    content = llm.mock_content("creative_plan", context)

    plan = CreativePlan(
        product_id=product.id,
        diagnosis_id=diagnosis.id,
        version=1,
        status="confirmed",
    )
    db.add(plan)
    db.flush()
    for index, scheme in enumerate(content.get("image_schemes") or [], start=1):
        db.add(
            ImageScheme(
                plan_id=plan.id,
                order_no=index,
                title=scheme["title"],
                layout=scheme["layout"],
                copy=scheme["copy"],
                main_selling_point=scheme["main_selling_point"],
                visual_tip=scheme["visual_tip"],
                status="confirmed",
            )
        )
    for index, script in enumerate(content.get("video_scripts") or [], start=1):
        row = VideoScript(
            plan_id=plan.id,
            order_no=index,
            title=script["title"],
            hook_3s=script["hook_3s"],
            closing_cta=script["closing_cta"],
            status="confirmed",
        )
        db.add(row)
        db.flush()
        for shot_no, shot in enumerate(script.get("shots") or [], start=1):
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
    db.flush()
    return plan


def seed_service_business(db: Session | None = None) -> None:
    """增量、幂等地补齐本地生活服务店铺、套餐、诊断与预置创意。"""
    own = db is None
    db = db or SessionLocal()
    try:
        operator = db.scalar(select(User).where(User.username == "operator"))
        manager = db.scalar(select(User).where(User.username == "manager"))
        created_by = (operator or manager)
        if created_by is None:
            return

        store_air = _ensure_local_store(db, "净呼吸除甲醛", "local_****8a20")
        store_laundry = _ensure_local_store(db, "洁净洗衣", "local_****6c31")

        air_product, _ = _ensure_service_product(
            db,
            store_air,
            "净呼吸除甲醛 · 全屋空气治理",
            "除甲醛服务",
            price_min=45,
            price_max=68,
            description=(
                "上门空气检测与全屋治理，按空间与污染源定制方案；"
                "提供第三方检测报告、治理后复检与质保期内免费返工。"
            ),
        )
        _ensure_service_skus(
            db,
            air_product,
            [
                (
                    {
                        "套餐": "全屋检测",
                        "计价单位": "元/3点",
                        "服务范围": "≤120㎡",
                        "时效": "上门 60 分钟",
                    },
                    299,
                ),
                (
                    {
                        "套餐": "全屋治理",
                        "计价单位": "元/㎡",
                        "服务范围": "按实际面积",
                        "时效": "24 小时内预约",
                    },
                    45,
                ),
                (
                    {
                        "套餐": "母婴急住治理",
                        "计价单位": "元/㎡",
                        "服务范围": "母婴家庭",
                        "时效": "复检合格后入住",
                    },
                    68,
                ),
            ],
        )
        _ensure_competitors(
            db,
            air_product,
            [
                {
                    "name": "美团 · 绿净环保除甲醛",
                    "price": 39,
                    "params_json": {"检测": "免费上门", "质保": "3 年", "治理工艺": "光触媒"},
                    "sales_volume": 860,
                    "rating": 4.6,
                },
                {
                    "name": "大众点评 · 深呼吸空气治理",
                    "price": 58,
                    "params_json": {"检测": "CMA 送检", "质保": "5 年", "复检": "治理后 1 次"},
                    "sales_volume": 420,
                    "rating": 4.7,
                },
            ],
        )
        air_diagnosis = _ensure_service_diagnosis(db, air_product, created_by.id)

        laundry_product, _ = _ensure_service_product(
            db,
            store_laundry,
            "洁净洗衣 · 上门取送",
            "洗衣服务",
            price_min=29,
            price_max=69,
            description=(
                "洗鞋、羽绒服与床品四件套上门取送；按面料标识洗护，"
                "满 ¥99 上门取送免运费，异常件先沟通。"
            ),
        )
        _ensure_service_skus(
            db,
            laundry_product,
            [
                (
                    {
                        "套餐": "洗鞋",
                        "计价单位": "元/双",
                        "服务范围": "运动鞋 / 帆布鞋",
                        "时效": "3 天取送",
                    },
                    29,
                ),
                (
                    {
                        "套餐": "羽绒服清洗",
                        "计价单位": "元/件",
                        "服务范围": "长短款同价",
                        "时效": "5 天取送",
                    },
                    49,
                ),
                (
                    {
                        "套餐": "四件套清洗",
                        "计价单位": "元/套",
                        "服务范围": "床单 / 被套 / 枕套",
                        "时效": "5 天取送",
                    },
                    69,
                ),
            ],
        )
        _ensure_competitors(
            db,
            laundry_product,
            [
                {
                    "name": "美团 · 快洗到家",
                    "price": 25,
                    "params_json": {"取送": "满 59 免运", "洗护": "普通干洗", "时效": "48 小时"},
                    "sales_volume": 1260,
                    "rating": 4.5,
                },
                {
                    "name": "大众点评 · 净衣坊",
                    "price": 39,
                    "params_json": {"取送": "满 99 免运", "洗护": "分面料洗护", "时效": "72 小时"},
                    "sales_volume": 680,
                    "rating": 4.8,
                },
            ],
        )
        laundry_diagnosis = _ensure_service_diagnosis(db, laundry_product, created_by.id)
        _ensure_service_plan(db, laundry_product, laundry_diagnosis)
        db.commit()
    finally:
        if own:
            db.close()


def reset_demo() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed()
