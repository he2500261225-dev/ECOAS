"""模拟素材生成器：图片输出 SVG 主图，视频输出 SVG 动效预览 + 脚本附件。

不调用任何外部图像/视频服务，产物仅用于演示异步任务与素材审核流程。
"""

from __future__ import annotations

import html
import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import ASSET_DIR
from ..models import Asset, ImageScheme, Product, VideoScript
from ..services.service_profiles import get_service_profile


def _esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _clip(text: object, limit: int) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned if len(cleaned) <= limit else f"{cleaned[:limit]}…"


def _wrap(text: object, width: int, max_lines: int) -> list[str]:
    """按字符数简单折行，够用即可，避免引入排版依赖。"""
    cleaned = " ".join(str(text or "").split())
    lines = [cleaned[i : i + width] for i in range(0, len(cleaned), width)] or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = f"{lines[-1][: max(0, width - 1)]}…"
    return lines


def _text_block(lines: list[str], x: int, y: int, line_height: int, size: int, fill: str, **attrs) -> str:
    extra = " ".join(f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items())
    parts = []
    for index, line in enumerate(lines):
        parts.append(
            f'<text x="{x}" y="{y + index * line_height}" font-size="{size}" fill="{fill}" '
            f'font-family="sans-serif" {extra}>{_esc(line)}</text>'
        )
    return "\n  ".join(parts)


def _next_version(db: Session, task) -> int:
    current = db.scalar(
        select(func.max(Asset.version)).where(
            Asset.product_id == task.product_id,
            Asset.source_type == task.source_type,
            Asset.source_id == task.source_id,
        )
    )
    return int(current or 0) + 1


def _write(filename: str, content: str) -> str:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / filename
    path.write_text(content, encoding="utf-8")
    return f"/files/assets/{filename}"


def _render_image_svg(product: Product, scheme: ImageScheme, version: int) -> str:
    copy_lines = _wrap(scheme.copy or scheme.title, 13, 2)
    layout_lines = _wrap(scheme.layout, 26, 3)
    tip_lines = _wrap(scheme.visual_tip, 30, 2)
    point_lines = _wrap(scheme.main_selling_point, 22, 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 900 900">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1220"/>
      <stop offset="55%" stop-color="#0f766e"/>
      <stop offset="100%" stop-color="#0ea5e9"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="900" height="900" fill="url(#bg)"/>
  <circle cx="720" cy="180" r="280" fill="url(#glow)"/>
  <circle cx="140" cy="780" r="240" fill="#ffffff" opacity="0.06"/>
  <text x="64" y="88" fill="#a7f3d0" font-size="24" font-family="sans-serif" letter-spacing="2">模拟生成 · 主图方案 v{version}</text>
  <text x="64" y="132" fill="#e2e8f0" opacity="0.85" font-size="26" font-family="sans-serif">{_esc(_clip(product.name, 30))}</text>
  <text x="64" y="206" fill="#ffffff" opacity="0.7" font-size="22" font-family="sans-serif" letter-spacing="2">{_esc(scheme.title)}</text>
  {_text_block(copy_lines, 64, 330, 92, 76, "#ffffff", font_weight="bold")}
  <rect x="64" y="500" width="760" height="128" rx="16" fill="#ffffff" opacity="0.12"/>
  <text x="88" y="540" fill="#a7f3d0" font-size="18" font-family="sans-serif" letter-spacing="1">核心卖点</text>
  {_text_block(point_lines, 88, 582, 32, 24, "#ffffff")}
  <rect x="64" y="660" width="760" height="96" rx="14" fill="#0b1220" opacity="0.32"/>
  <text x="88" y="696" fill="#94a3b8" font-size="17" font-family="sans-serif">构图说明</text>
  {_text_block(layout_lines, 88, 726, 24, 18, "#cbd5e1")}
  <text x="64" y="806" fill="#a7f3d0" font-size="17" font-family="sans-serif">视觉提示 · {_esc(tip_lines[0])}</text>
  <text x="64" y="838" fill="#94a3b8" font-size="15" font-family="sans-serif">方案 #{scheme.order_no} · {_esc(_clip(product.name, 24))} · AI 模拟生成，仅供方案评审</text>
</svg>"""


def _render_video_svg(product: Product, script: VideoScript, version: int, total_duration: int) -> str:
    hook_lines = _wrap(script.hook_3s, 18, 2)
    cta_line = _clip(script.closing_cta, 34)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <defs>
    <linearGradient id="vbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1220"/>
      <stop offset="60%" stop-color="#1e1b4b"/>
      <stop offset="100%" stop-color="#7c3aed"/>
    </linearGradient>
    <radialGradient id="vglow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0%" stop-color="#a78bfa" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#a78bfa" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="960" height="540" fill="url(#vbg)"/>
  <circle cx="760" cy="140" r="180" fill="url(#vglow)">
    <animate attributeName="r" values="160;200;160" dur="6s" repeatCount="indefinite"/>
  </circle>
  <circle cx="200" cy="440" r="120" fill="#22d3ee" opacity="0.12">
    <animate attributeName="opacity" values="0.06;0.2;0.06" dur="4s" repeatCount="indefinite"/>
  </circle>
  <rect x="0" y="0" width="960" height="6" fill="#22d3ee" opacity="0.7">
    <animate attributeName="width" values="0;960" dur="8s" repeatCount="indefinite"/>
  </rect>
  <text x="56" y="72" fill="#c4b5fd" font-size="20" font-family="sans-serif" letter-spacing="2">模拟视频预览 · 动效分镜 v{version}</text>
  <text x="56" y="112" fill="#e2e8f0" opacity="0.82" font-size="22" font-family="sans-serif">{_esc(_clip(product.name, 28))} · {_esc(_clip(script.title, 20))}</text>
  <text x="56" y="196" fill="#94a3b8" font-size="17" font-family="sans-serif" letter-spacing="1">前 3 秒钩子</text>
  {_text_block(hook_lines, 56, 258, 56, 42, "#ffffff", font_weight="bold")}
  <rect x="56" y="372" width="848" height="72" rx="14" fill="#0b1220" opacity="0.4"/>
  <text x="80" y="404" fill="#7dd3fc" font-size="17" font-family="sans-serif" letter-spacing="1">结尾促单</text>
  <text x="80" y="430" fill="#e2e8f0" font-size="20" font-family="sans-serif">{_esc(cta_line)}</text>
  <text x="56" y="492" fill="#94a3b8" font-size="15" font-family="sans-serif">分镜 {len(script.shots)} 个 · 总时长约 {total_duration}s · 脚本 JSON / Markdown 可在任务详情下载</text>
  <text x="904" y="492" fill="#c4b5fd" font-size="15" font-family="sans-serif" text-anchor="end">AI 模拟生成，仅供方案评审</text>
</svg>"""


def _service_colors(profile: dict) -> dict:
    if profile.get("visual_template") == "laundry-care":
        return {
            "bg1": "#0b1f3a",
            "bg2": "#1d4ed8",
            "bg3": "#38bdf8",
            "accent": "#bae6fd",
            "badge": "衣物洗护 / 上门取送",
        }
    return {
        "bg1": "#062a2a",
        "bg2": "#0f766e",
        "bg3": "#22d3ee",
        "accent": "#a7f3d0",
        "badge": "洁净空气 / 检测质保",
    }


def _render_service_image_svg(
    product: Product, scheme: ImageScheme, version: int, profile: dict
) -> str:
    colors = _service_colors(profile)
    copy_lines = _wrap(scheme.copy or scheme.title, 13, 2)
    layout_lines = _wrap(scheme.layout, 26, 3)
    point_lines = _wrap(scheme.main_selling_point, 22, 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 900 900">
  <defs>
    <linearGradient id="sbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{colors['bg1']}"/>
      <stop offset="55%" stop-color="{colors['bg2']}"/>
      <stop offset="100%" stop-color="{colors['bg3']}"/>
    </linearGradient>
  </defs>
  <rect width="900" height="900" fill="url(#sbg)"/>
  <circle cx="720" cy="180" r="300" fill="#ffffff" opacity="0.08"/>
  <circle cx="150" cy="780" r="240" fill="#ffffff" opacity="0.06"/>
  <rect x="64" y="64" width="300" height="44" rx="22" fill="#ffffff" opacity="0.16"/>
  <text x="88" y="94" fill="{colors['accent']}" font-size="19" font-family="sans-serif" letter-spacing="2">模拟生成 · 获客素材方案 v{version}</text>
  <text x="64" y="156" fill="#ffffff" opacity="0.86" font-size="26" font-family="sans-serif">{_esc(_clip(product.name, 28))}</text>
  <text x="64" y="214" fill="{colors['accent']}" font-size="20" font-family="sans-serif" letter-spacing="2">{_esc(profile['category'])} · {_esc(colors['badge'])}</text>
  <text x="64" y="286" fill="#ffffff" opacity="0.72" font-size="22" font-family="sans-serif">{_esc(scheme.title)}</text>
  {_text_block(copy_lines, 64, 392, 88, 74, "#ffffff", font_weight="bold")}
  <rect x="64" y="548" width="760" height="118" rx="16" fill="#ffffff" opacity="0.13"/>
  <text x="88" y="586" fill="{colors['accent']}" font-size="18" font-family="sans-serif" letter-spacing="1">信任点 / 核心卖点</text>
  {_text_block(point_lines, 88, 628, 30, 23, "#ffffff")}
  <rect x="64" y="686" width="760" height="92" rx="14" fill="#03131f" opacity="0.34"/>
  <text x="88" y="720" fill="#cbd5e1" font-size="17" font-family="sans-serif">服务场景与构图</text>
  {_text_block(layout_lines, 88, 750, 23, 17, "#e2e8f0")}
  <text x="64" y="834" fill="{colors['accent']}" font-size="16" font-family="sans-serif">模拟生成，仅供方案评审 · {_esc(_clip(product.name, 22))} · 获客素材 #{scheme.order_no}</text>
</svg>"""


def _render_service_video_svg(
    product: Product, script: VideoScript, version: int, total_duration: int, profile: dict
) -> str:
    colors = _service_colors(profile)
    hook_lines = _wrap(script.hook_3s, 18, 2)
    cta_line = _clip(script.closing_cta, 34)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
  <defs>
    <linearGradient id="svbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{colors['bg1']}"/>
      <stop offset="60%" stop-color="{colors['bg2']}"/>
      <stop offset="100%" stop-color="{colors['bg3']}"/>
    </linearGradient>
  </defs>
  <rect width="960" height="540" fill="url(#svbg)"/>
  <circle cx="780" cy="130" r="180" fill="#ffffff" opacity="0.10">
    <animate attributeName="r" values="160;200;160" dur="6s" repeatCount="indefinite"/>
  </circle>
  <circle cx="180" cy="450" r="130" fill="#ffffff" opacity="0.08">
    <animate attributeName="opacity" values="0.04;0.16;0.04" dur="4s" repeatCount="indefinite"/>
  </circle>
  <rect x="0" y="0" width="960" height="6" fill="{colors['accent']}" opacity="0.8">
    <animate attributeName="width" values="0;960" dur="8s" repeatCount="indefinite"/>
  </rect>
  <text x="56" y="72" fill="{colors['accent']}" font-size="20" font-family="sans-serif" letter-spacing="2">模拟视频预览 · 获客视频分镜 v{version}</text>
  <text x="56" y="112" fill="#e2e8f0" opacity="0.86" font-size="22" font-family="sans-serif">{_esc(_clip(product.name, 26))} · {_esc(_clip(script.title, 20))}</text>
  <text x="56" y="192" fill="#cbd5e1" font-size="17" font-family="sans-serif" letter-spacing="1">前 3 秒钩子</text>
  {_text_block(hook_lines, 56, 256, 56, 40, "#ffffff", font_weight="bold")}
  <rect x="56" y="366" width="848" height="76" rx="14" fill="#03131f" opacity="0.42"/>
  <text x="80" y="398" fill="{colors['accent']}" font-size="17" font-family="sans-serif" letter-spacing="1">结尾预约动作</text>
  <text x="80" y="426" fill="#e2e8f0" font-size="20" font-family="sans-serif">{_esc(cta_line)}</text>
  <text x="56" y="492" fill="#e2e8f0" opacity="0.8" font-size="15" font-family="sans-serif">分镜 {len(script.shots)} 个 · 总时长约 {total_duration}s · 脚本 JSON / Markdown 可在任务详情下载</text>
  <text x="904" y="492" fill="{colors['accent']}" font-size="15" font-family="sans-serif" text-anchor="end">模拟生成，仅供方案评审</text>
</svg>"""


def generate_media(db: Session, task) -> dict:
    """按任务快照生成素材文件，返回待写入 assets 的字段与附件列表。"""
    product = db.get(Product, task.product_id)
    if product is None:
        raise ValueError("商品不存在，无法生成素材")

    profile = get_service_profile(product.category)
    is_service = profile is not None
    version = _next_version(db, task)
    attachments: list[dict] = []

    if task.source_type == "image_scheme":
        scheme = db.get(ImageScheme, task.source_id)
        if scheme is None:
            raise ValueError("主图方案不存在，无法生成素材")
        filename = f"p{product.id}_img{scheme.id}_v{version}.svg"
        if is_service:
            content = _render_service_image_svg(product, scheme, version, profile)
        else:
            content = _render_image_svg(product, scheme, version)
        url = _write(filename, content)
        return {
            "asset": {
                "product_id": product.id,
                "type": "image",
                "source_type": task.source_type,
                "source_id": task.source_id,
                "filename": filename,
                "file_path": url,
                "mime": "image/svg+xml",
                "version": version,
                "status": "pending_review",
                "tags_json": ["模拟生成", "获客素材"] if is_service else ["模拟生成", "主图"],
            },
            "attachments": attachments,
            "meta": {"scheme_title": scheme.title, "order_no": scheme.order_no},
        }

    if task.source_type == "video_script":
        script = db.get(VideoScript, task.source_id)
        if script is None:
            raise ValueError("视频脚本不存在，无法生成素材")
        shots = list(script.shots)
        total_duration = sum(int(shot.duration_sec or 0) for shot in shots)
        filename = f"p{product.id}_vid{script.id}_v{version}.svg"
        if is_service:
            content = _render_service_video_svg(
                product, script, version, total_duration, profile
            )
        else:
            content = _render_video_svg(product, script, version, total_duration)
        url = _write(filename, content)

        json_name = f"p{product.id}_vid{script.id}_v{version}.json"
        md_name = f"p{product.id}_vid{script.id}_v{version}.md"
        payload = {
            "product": {"id": product.id, "name": product.name},
            "script": {
                "id": script.id,
                "title": script.title,
                "hook_3s": script.hook_3s,
                "closing_cta": script.closing_cta,
            },
            "shots": [
                {
                    "shot_no": shot.shot_no,
                    "duration_sec": shot.duration_sec,
                    "scene_desc": shot.scene_desc,
                    "voiceover": shot.voiceover,
                    "cta_line": shot.cta_line,
                }
                for shot in shots
            ],
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
            "note": "模拟生成，仅用于演示与方案评审",
        }
        json_url = _write(json_name, json.dumps(payload, ensure_ascii=False, indent=2))

        md_lines = [
            f"# {product.name} · {script.title}",
            "",
            "> 模拟生成的分镜脚本，仅用于演示与方案评审。",
            "",
            "## 前 3 秒钩子",
            "",
            script.hook_3s,
            "",
            "## 分镜脚本",
            "",
            "| 镜号 | 时长(s) | 画面描述 | 口播台词 | 促单话术 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for shot in shots:
            cells = [
                str(shot.shot_no),
                str(shot.duration_sec),
                shot.scene_desc,
                shot.voiceover,
                shot.cta_line,
            ]
            md_lines.append("| " + " | ".join(cell.replace("|", "｜") for cell in cells) + " |")
        md_lines += ["", "## 结尾促单", "", script.closing_cta, ""]
        md_url = _write(md_name, "\n".join(md_lines))

        attachments = [
            {"kind": "script_json", "name": json_name, "url": json_url},
            {"kind": "script_markdown", "name": md_name, "url": md_url},
        ]
        return {
            "asset": {
                "product_id": product.id,
                "type": "video",
                "source_type": task.source_type,
                "source_id": task.source_id,
                "filename": filename,
                "file_path": url,
                "mime": "image/svg+xml",
                "version": version,
                "status": "pending_review",
                "tags_json": ["模拟生成", "获客素材"] if is_service else ["模拟生成", "视频"],
            },
            "attachments": attachments,
            "meta": {
                "script_title": script.title,
                "shot_count": len(shots),
                "total_duration": total_duration,
            },
        }

    raise ValueError(f"不支持的任务来源：{task.source_type}")
