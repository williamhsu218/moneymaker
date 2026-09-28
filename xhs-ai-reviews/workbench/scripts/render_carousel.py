#!/usr/bin/env python3
"""Render the full image set of a post (cover, rules, screenshot frames,
comparison grids, result table, conclusion, text cards, photos).

Before review every image carries a draft band and stamp. After the one-click
review, rendering again produces the final set and records the review
fingerprint in images/render.json so the gate can tell the images match
exactly the reviewed content.

    python scripts/render_carousel.py post-01-weekly-report
    python scripts/render_carousel.py post-01-weekly-report --html-only
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import cards
from scripts.generate_post_assets import export_many
from scripts.project import IMAGE_EXTS, SHARED_SCOPE, Project, ProjectError, image_size, load_json, now_iso, sha256_file, write_json, write_text
from scripts.readiness import assess_post_readiness

FORMAT_EYEBROW = {"cmp": "横评", "how": "教程", "new": "新品实测", "recap": "复盘"}


def _evidence_path(project: Project, post_id: str, manifest: Dict[str, Any], scope: str, key: str) -> Optional[Path]:
    if scope == SHARED_SCOPE:
        relative = (manifest.get("shared") or {}).get(key)
    else:
        relative = (((manifest.get("tools") or {}).get(scope) or {}).get("files") or {}).get(key)
    if not relative:
        return None
    base = project.post_dir(post_id) / "evidence" / scope
    try:
        path = project.resolve_inside(relative, base)
    except ProjectError:
        return None
    if path.parent != base.resolve():
        return None
    return path if path.is_file() else None


def _photo(post_dir: Path, index: int) -> Optional[Path]:
    folder = post_dir / "photos"
    for stem in (f"{index:02d}", str(index)):
        for ext in IMAGE_EXTS:
            candidate = folder / f"{stem}.{ext}"
            if candidate.is_file():
                return candidate
    return None


def _meta_line(entry: Dict[str, Any]) -> str:
    unknown = {"未显示", "界面未显示", "未知", "-", "—"}
    parts = [value for value in (entry.get("model"), entry.get("version"), entry.get("platform")) if str(value or "").strip() not in unknown]
    tested = str(entry.get("tested_at") or "")[:10]
    if tested:
        parts.append(f"测试于 {tested}")
    return " · ".join(part for part in parts if part) or "模型、版本待录入"


def _redacted_evidence(project: Project, post_id: str, temp_dir: Path) -> Dict[tuple[str, str], Path]:
    """Rasterize masks before embedding images in shareable HTML or final PNGs.

    The source screenshot stays in evidence; the temporary HTML that contains
    its raw bytes is deleted when rendering ends. Final HTML embeds only the
    flattened, masked PNG.
    """
    post_dir = project.post_dir(post_id)
    topic = project.post_topic(post_id)
    manifest = load_json(post_dir / "evidence" / "manifest.json", {}) or {}
    highlights = load_json(post_dir / "highlights.json", {}) or {}
    targets = [(tool, spec["key"]) for tool in project.post_tools(post_id)
               for spec in topic.get("evidence", {}).get("per_tool", []) if spec.get("kind") == "image"]
    targets += [(SHARED_SCOPE, spec["key"]) for spec in topic.get("evidence", {}).get("shared", []) if spec.get("kind") == "image"]
    overrides: Dict[tuple[str, str], Path] = {}
    for index, (scope, key) in enumerate(targets):
        masks = ((highlights.get(scope) or {}).get(key) or {}).get("masks") or []
        if not masks:
            continue
        source = _evidence_path(project, post_id, manifest, scope, key)
        if source is None:
            continue  # Missing evidence already blocks final publication.
        size = image_size(source)
        if not size or min(size) <= 0:
            raise ProjectError(f"{scope}/{key} 的图片尺寸无法读取，不能安全遮挡")
        original_w, original_h = size
        width = max(500, original_w)
        height = round(original_h * width / original_w)
        if height < 1:
            raise ProjectError(f"{scope}/{key} 的图片尺寸无效")
        scale = width / original_w
        try:
            rects = cards.privacy_mask_rects(masks, original_w, original_h)
        except ValueError as exc:
            raise ProjectError(f"{scope}/{key} 的隐私遮挡坐标无效") from exc
        uri = cards.data_uri(source)
        if not uri:
            raise ProjectError(f"{scope}/{key} 不是可渲染的截图，不能安全遮挡")
        cover = "".join(
            f'<div style="position:absolute;left:{round(x * scale)}px;top:{round(y * scale)}px;'
            f'width:{round(w * scale)}px;height:{round(h * scale)}px;background:#151515"></div>'
            for x, y, w, h in rects
        )
        html = (f'<!doctype html><html><head><meta charset="utf-8"><style>'
                f'*{{box-sizing:border-box}}html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden}}'
                f'img{{display:block;width:{width}px;height:{height}px}}</style></head><body>'
                f'<img src="{uri}">{cover}</body></html>')
        source_html = temp_dir / f"mask-{index}.html"
        masked_png = temp_dir / f"mask-{index}.png"
        write_text(source_html, html)
        ok, _ = export_many([(source_html, masked_png)], width=width, height=height)
        if not ok[0] or image_size(masked_png) != (width, height):
            raise ProjectError(f"{scope}/{key} 的隐私遮挡图生成失败；请检查 Chrome，终版未更新")
        overrides[(scope, key)] = masked_png
    return overrides


def build_items(project: Project, post_id: str, *, draft: bool, image_overrides: Optional[Dict[tuple[str, str], Path]] = None) -> List[Dict[str, Any]]:
    post_dir = project.post_dir(post_id)
    post = project.load_post(post_id)
    topic = project.post_topic(post_id)
    brand = project.brand()
    tools = project.post_tools(post_id)
    manifest = load_json(post_dir / "evidence" / "manifest.json", {}) or {}
    scorecard = load_json(post_dir / "scorecard.json", {}) or {}
    post_cards = load_json(post_dir / "cards.json", {}) or {}
    highlights = load_json(post_dir / "highlights.json", {}) or {}
    image_overrides = image_overrides or {}

    def evidence_image(scope: str, key: str) -> Optional[Path]:
        return image_overrides.get((scope, key)) or _evidence_path(project, post_id, manifest, scope, key)
    inner = brand.get("inner_palette") or {}
    palettes = brand.get("palettes") or {}
    cover_cfg = post.get("cover") or {}
    palette_name = cover_cfg.get("palette") or "yellow"
    palette = palettes.get(palette_name) or next(iter(palettes.values()))
    tool_names = {tool: project.tool_name(tool) for tool in tools}
    results = scorecard.get("tool_results") or {}
    tool_rows = [{"id": tool, "name": tool_names[tool], "result": results.get(tool) or {}} for tool in tools]
    eyebrow = f"第{topic['id']}期 · {FORMAT_EYEBROW.get(topic.get('format'), '')}"
    footer = f"{brand.get('account_name', '')}｜{brand.get('tagline', '')}"
    date_note = scorecard.get("evaluation_date") or "（测试日期待定）"

    specs: List[Dict[str, Any]] = []
    for position, image in enumerate(topic.get("images", [])):
        kind = image.get("kind")
        if kind == "evidence_each":
            for tool in tools:
                specs.append({**image, "tool": tool, "position": position})
        else:
            specs.append({**image, "position": position})
    total = len(specs)
    items = []
    for number, spec in enumerate(specs, 1):
        kind = spec.get("kind")
        label = spec.get("label", "")
        common = {"eyebrow": eyebrow, "footer": footer, "page": f"{number:02d}/{total:02d}", "draft": draft}
        slug = kind
        if kind == "cover":
            html = cards.cover_html(
                tag=cover_cfg.get("tag") or (topic.get("cover") or {}).get("tag", ""),
                lines=cover_cfg.get("lines") or (topic.get("cover") or {}).get("lines", []),
                tools=[tool_names[tool] for tool in tools],
                palette=palette, account_name=brand.get("account_name", ""), tagline=brand.get("tagline", ""),
                style=palette_name, draft=draft,
            )
        elif kind == "rules":
            html = cards.rules_html(inner, topic.get("rules_card") or {"title": label, "rows": []}, **common)
        elif kind == "evidence_each":
            tool = spec["tool"]
            slug = f"evidence-{tool}"
            entry = (manifest.get("tools") or {}).get(tool) or {}
            html = cards.evidence_html(
                inner, tool_name=tool_names[tool], meta=_meta_line(entry), label=label,
                image=evidence_image(tool, spec["key"]),
                highlights=((highlights.get(tool) or {}).get(spec["key"])), **common,
            )
        elif kind in ("evidence_pair", "evidence_grid"):
            if kind == "evidence_pair":
                picked = [tool for tool in (post.get("picks") or {}).get(str(spec["position"]), []) if tool in tools]
                chosen = (picked or tools)[:2]
            else:
                chosen = tools[:4]
            cells = []
            if spec.get("shared"):
                cells.append({"name": "原图", "image": evidence_image(SHARED_SCOPE, spec["shared"]), "highlights": (highlights.get(SHARED_SCOPE) or {}).get(spec["shared"])})
                chosen = chosen[:3]
            for tool in chosen:
                cells.append({
                    "name": tool_names[tool],
                    "image": evidence_image(tool, spec["key"]),
                    "highlights": (highlights.get(tool) or {}).get(spec["key"]),
                })
            slug = f"compare-{spec['position'] + 1}"
            html = cards.grid_html(inner, label=label, cells=cells, **common)
        elif kind == "scorecard":
            html = cards.scorecard_html(
                inner, label=label, tools=tool_rows, checks=scorecard.get("checks") or topic.get("checks") or {},
                overall_label=(scorecard.get("overall") or topic.get("overall") or {}).get("label", "总评"),
                note=f"只代表 {date_note} 这次测试的结果，不代表工具的长期表现", **common,
            )
        elif kind == "conclusion":
            html = cards.conclusion_html(
                inner, label=label, tools=tool_rows,
                overall_label=(scorecard.get("overall") or topic.get("overall") or {}).get("label", "总评"),
                closer=brand.get("closer", ""), **common,
            )
        elif kind == "text_card":
            card_id = spec.get("card", "")
            card = post_cards.get(card_id) or (topic.get("cards") or {}).get(card_id) or {"title": label, "lines": []}
            slug = f"card-{card_id}"
            html = cards.text_card_html(inner, card=card, label=label, **common)
        elif kind == "photo":
            index = int(spec.get("index", 1))
            caption = ((post_cards.get("photo_captions") or {}).get(str(index))) or label
            slug = f"photo-{index}"
            html = cards.photo_html(inner, image=_photo(post_dir, index), caption=caption, draft=draft, page_label=common["page"])
        else:
            continue
        items.append({"index": number, "kind": kind, "label": label, "slug": slug, "html": html, "tool": spec.get("tool")})
    return items


def render_post(project: Project, post_id: str, *, export: bool = True) -> Dict[str, Any]:
    post_dir = project.post_dir(post_id)
    readiness = assess_post_readiness(project, post_id)
    draft = not readiness["content_verified"]
    images_dir = post_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    previous = load_json(images_dir / "render.json", {}) or {}
    for item in previous.get("files", []):
        for name in (item.get("html"), item.get("png")):
            if name and "/" not in name and (images_dir / name).is_file():
                (images_dir / name).unlink()
    with tempfile.TemporaryDirectory(prefix="xhs-masked-") as temporary:
        overrides = _redacted_evidence(project, post_id, Path(temporary))
        items = build_items(project, post_id, draft=draft, image_overrides=overrides)
    pairs = []
    files = []
    for item in items:
        stem = f"{item['index']:02d}-{item['slug']}"
        html_path = images_dir / f"{stem}.html"
        png_path = images_dir / f"{stem}.png"
        write_text(html_path, item["html"])
        pairs.append((html_path, png_path))
        files.append({"index": item["index"], "kind": item["kind"], "label": item["label"], "tool": item.get("tool"), "html": html_path.name, "png": png_path.name})
    engine = "skipped"
    png_ok = False
    if export and pairs:
        results, engine = export_many(pairs)
        png_ok = all(results)
        for entry, ok in zip(files, results):
            entry["sha256"] = sha256_file(images_dir / entry["png"]) if ok else None
    render = {
        "draft": draft,
        "review_fingerprint": None if draft else readiness.get("review_fingerprint"),
        "generated_at": now_iso(),
        "png_ok": png_ok,
        "engine": engine,
        "files": files,
    }
    write_json(images_dir / "render.json", render)
    return {"status": "rendered" if (png_ok or not export) else "png_failed", "draft": draft, "engine": engine, "files": files, "readiness": assess_post_readiness(project, post_id)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成一篇笔记的整套 1080×1440 图片")
    parser.add_argument("post_id")
    parser.add_argument("--html-only", action="store_true", help="只生成 HTML，不导出 PNG")
    args = parser.parse_args(argv)
    result = render_post(Project(), args.post_id, export=not args.html_only)
    print(json.dumps({key: result[key] for key in ("status", "draft", "engine")}, ensure_ascii=False))
    for entry in result["files"]:
        print(f"  {entry['png']}  {entry['label']}")
    if result["status"] == "png_failed":
        print("PNG 导出失败：请安装 Google Chrome（或 pip install playwright && playwright install chromium）后重试。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
