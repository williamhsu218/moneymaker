"""HTML for every 1080×1440 image of a post: cover, rules, screenshot frames,
comparison grids, result table, conclusion, text cards and photos.

All functions return a complete standalone HTML document. Images are embedded
as data URIs so headless Chrome can screenshot them from a file:// page.
"""
from __future__ import annotations

import base64
import html
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from scripts.project import image_kind, image_size
except ImportError:  # pragma: no cover
    from project import image_kind, image_size  # type: ignore

W, H = 1080, 1440
FONT_STACK = '"PingFang SC", "Noto Sans CJK SC", "Noto Sans SC", "Hiragino Sans GB", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif'
DRAFT_TEXT = "草稿 · 待实测，不可发布"
MIME = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def text_width(text: str) -> float:
    """Approximate rendered width in em: CJK = 1, Latin/digits ≈ 0.58."""
    width = 0.0
    for ch in str(text):
        if ord(ch) < 128:
            width += 0.36 if ch in " .,:;!|'" else 0.6
        else:
            width += 1.0
    return max(width, 1.0)


def data_uri(path: Optional[Path]) -> Optional[str]:
    if not path or not Path(path).is_file():
        return None
    kind = image_kind(Path(path))
    if kind not in MIME:
        return None
    return f"data:{MIME[kind]};base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def privacy_mask_rects(masks: Sequence[Dict[str, Any]], width: int, height: int) -> List[tuple[int, int, int, int]]:
    """Pixel rectangles with a small safety margin, clipped to the original image."""
    rectangles = []
    for mask in masks:
        try:
            x, y, w, h = (float(mask[key]) for key in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Invalid privacy mask") from exc
        if (not all(math.isfinite(value) for value in (x, y, w, h)) or x < 0 or y < 0
                or w <= 0 or h <= 0 or x + w > 1.0001 or y + h > 1.0001):
            raise ValueError("Privacy mask is outside its image")
        left = max(0, math.floor(x * width) - 3)
        top = max(0, math.floor(y * height) - 3)
        right = min(width, math.ceil((x + w) * width) + 3)
        bottom = min(height, math.ceil((y + h) * height) + 3)
        rectangles.append((left, top, right - left, bottom - top))
    return rectangles


def page(body: str, *, bg: str, ink: str, extra_css: str = "", title: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width={W}, height={H}">
<title>{esc(title)}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; }}
body {{ background: {bg}; color: {ink}; font-family: {FONT_STACK}; -webkit-font-smoothing: antialiased; position: relative; }}
.draft-band {{ position: absolute; left: 0; right: 0; top: 0; height: 72px; background: #b3391f; color: #fff; font-size: 34px; font-weight: 800; letter-spacing: 4px; display: flex; align-items: center; justify-content: center; z-index: 20; }}
.draft-stamp {{ position: absolute; right: 40px; bottom: 150px; transform: rotate(-12deg); border: 6px solid rgba(179,57,31,.85); color: rgba(179,57,31,.9); font-size: 44px; font-weight: 900; padding: 10px 26px; border-radius: 14px; z-index: 20; background: rgba(255,255,255,.55); }}
{extra_css}
</style></head><body>
{body}
</body></html>"""


def draft_marks(draft: bool) -> str:
    return f'<div class="draft-band">{DRAFT_TEXT}</div><div class="draft-stamp">草稿</div>' if draft else ""


# ----------------------------------------------------------------------- cover
def cover_html(*, tag: str, lines: Sequence[str], tools: Sequence[str], palette: Dict[str, str], account_name: str, tagline: str, style: str = "yellow", draft: bool = True) -> str:
    lines = [str(line) for line in lines if str(line).strip()] or ["待定标题"]
    widest = max(text_width(line) for line in lines)
    size = int(min(196, 940 / widest, 820 / (len(lines) * 1.14)))
    rendered = []
    for index, line in enumerate(lines):
        content = esc(line)
        if index == len(lines) - 1:
            content = f'<span class="em">{content}</span>'
        rendered.append(f'<div class="line">{content}</div>')
    if style == "dark":
        em_css = f".em {{ color: {palette['accent']}; }}"
    elif style == "mint":
        em_css = ".em { background: #ffffff; padding: 0 .12em; border-radius: .08em; }"
    else:
        em_css = f".em {{ box-shadow: inset 0 -0.3em 0 {palette['accent']}; }}"
    chips = "".join(f'<span class="chip">{esc(tool)}</span>' for tool in tools)
    css = f"""
.wrap {{ position: absolute; inset: 0; padding: {140 if draft else 96}px 76px 88px; display: flex; flex-direction: column; justify-content: space-between; }}
.top {{ display: flex; justify-content: space-between; align-items: center; gap: 24px; }}
.tag {{ background: {palette['tag_bg']}; color: {palette['tag_ink']}; font-size: 50px; font-weight: 900; padding: 16px 34px; border-radius: 14px; letter-spacing: 2px; }}
.brand {{ font-size: 36px; font-weight: 800; opacity: .82; }}
.headline {{ font-size: {size}px; font-weight: 900; line-height: 1.14; letter-spacing: -1px; }}
.line {{ white-space: nowrap; }}
{em_css}
.chips {{ display: flex; flex-wrap: wrap; gap: 18px; margin-bottom: 30px; }}
.chip {{ background: {palette['chip_bg']}; color: {palette['chip_ink']}; font-size: 40px; font-weight: 700; padding: 12px 26px; border-radius: 999px; }}
.tagline {{ font-size: 32px; font-weight: 600; opacity: .72; letter-spacing: 2px; }}
"""
    body = f"""{draft_marks(draft)}
<div class="wrap">
  <div class="top"><span class="tag">{esc(tag)}</span><span class="brand">{esc(account_name)}</span></div>
  <div class="headline">{''.join(rendered)}</div>
  <div><div class="chips">{chips}</div><div class="tagline">{esc(tagline)}</div></div>
</div>"""
    return page(body, bg=palette["bg"], ink=palette["ink"], extra_css=css, title=" ".join(lines))


# ------------------------------------------------------------------ inner base
def inner_css(p: Dict[str, str], draft: bool) -> str:
    return f"""
.wrap {{ position: absolute; inset: 0; padding: {130 if draft else 80}px 64px 64px; display: flex; flex-direction: column; }}
.eyebrow {{ font-size: 30px; font-weight: 700; color: {p['accent']}; letter-spacing: 3px; margin-bottom: 14px; }}
.title {{ font-size: 72px; font-weight: 900; line-height: 1.18; margin-bottom: 40px; }}
.content {{ flex: 1; min-height: 0; display: flex; flex-direction: column; }}
.foot {{ display: flex; justify-content: space-between; align-items: center; font-size: 28px; color: {p['muted']}; padding-top: 28px; border-top: 2px solid {p['line']}; margin-top: 28px; }}
.foot b {{ color: {p['ink']}; }}
.note {{ font-size: 32px; color: {p['muted']}; margin-top: 26px; line-height: 1.5; }}
.placeholder {{ flex: 1; border: 6px dashed {p['line']}; border-radius: 28px; display: flex; align-items: center; justify-content: center; font-size: 48px; color: {p['muted']}; font-weight: 800; text-align: center; padding: 40px; }}
"""


def inner_page(p: Dict[str, str], *, eyebrow: str, title: str, content: str, footer_left: str, page_label: str, draft: bool, css: str = "") -> str:
    body = f"""{draft_marks(draft)}
<div class="wrap">
  <div class="eyebrow">{esc(eyebrow)}</div>
  <div class="title">{esc(title)}</div>
  <div class="content">{content}</div>
  <div class="foot"><span><b>{esc(footer_left)}</b></span><span>{esc(page_label)}</span></div>
</div>"""
    return page(body, bg=p["bg"], ink=p["ink"], extra_css=inner_css(p, draft) + css, title=title)


def rules_html(p: Dict[str, str], rules: Dict[str, Any], **common: Any) -> str:
    rows = "".join(
        f'<div class="row"><div class="in">{esc(row.get("in", ""))}</div><div class="arrow">→</div><div class="out">{esc(row.get("out", ""))}</div></div>'
        for row in rules.get("rows", [])
    )
    count = max(1, len(rules.get("rows", [])))
    font = 42 if count <= 3 else 38 if count == 4 else 34
    css = f"""
.heads {{ display: grid; grid-template-columns: 1fr 60px 1fr; font-size: 30px; font-weight: 800; color: {p['muted']}; padding: 0 30px 16px; }}
.rows {{ display: flex; flex-direction: column; gap: 22px; }}
.row {{ display: grid; grid-template-columns: 1fr 60px 1fr; align-items: center; background: {p['surface']}; border-radius: 22px; border-left: 12px solid {p['warn']}; padding: 30px; font-size: {font}px; line-height: 1.38; font-weight: 700; }}
.arrow {{ color: {p['muted']}; text-align: center; }}
.out {{ color: {p['warn']}; }}
"""
    content = f"""<div class="heads"><span>{esc(rules.get('left', ''))}</span><span></span><span>{esc(rules.get('right', ''))}</span></div>
<div class="rows">{rows}</div>{f'<div class="note">{esc(rules.get("note"))}</div>' if rules.get('note') else ''}"""
    return inner_page(p, eyebrow=common["eyebrow"], title=rules.get("title", "测试规则"), content=content, footer_left=common["footer"], page_label=common["page"], draft=common["draft"], css=css)


def _image_box(path: Optional[Path], box_w: int, box_h: int, highlights: Optional[Dict[str, Any]], accent: str, empty_label: str) -> str:
    """An image contained in a box, with crop, opaque privacy masks and highlights."""
    uri = data_uri(path)
    if not uri:
        return f'<div class="placeholder" style="width:{box_w}px;height:{box_h}px;flex:none">{esc(empty_label)}</div>'
    size = image_size(Path(path)) or (box_w, box_h)
    natural_w, natural_h = max(1, size[0]), max(1, size[1])
    crop = (highlights or {}).get("crop") or {}
    y0 = min(max(float(crop.get("y0", 0.0)), 0.0), 0.95)
    y1 = min(max(float(crop.get("y1", 1.0)), y0 + 0.05), 1.0)
    visible_h = natural_h * (y1 - y0)
    scale = min(box_w / natural_w, box_h / visible_h)
    shown_w, shown_h = natural_w * scale, visible_h * scale
    left = (box_w - shown_w) / 2
    top = (box_h - shown_h) / 2
    full_h = natural_h * scale
    offset = -y0 * full_h
    masks = []
    for mx, my, mw, mh in privacy_mask_rects((highlights or {}).get("masks") or [], natural_w, natural_h):
        masks.append(
            f'<div class="privacy-mask" style="left:{mx * scale:.1f}px;top:{my * scale + offset:.1f}px;'
            f'width:{mw * scale:.1f}px;height:{mh * scale:.1f}px"></div>'
        )
    boxes = []
    number = 0
    for item in (highlights or {}).get("boxes", []) or []:
        try:
            x, y, w, h = (float(item[k]) for k in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError):
            continue
        by = (y - y0) / (y1 - y0) * shown_h
        bh = h / (y1 - y0) * shown_h
        if by + bh < 0 or by > shown_h:
            continue
        number += 1
        bx = left + x * shown_w
        boxes.append(f'<div class="hl" style="left:{bx:.1f}px;top:{top + by:.1f}px;width:{w * shown_w:.1f}px;height:{bh:.1f}px;border-color:{accent}"></div>')
        # Number badge sits just left of the box so it never covers the first characters;
        # falls back to the box corner when there is no margin beside the screenshot.
        if bx - 58 >= 0:
            nx, ny = bx - 58, top + by + min(bh / 2, 32) - 24
        else:
            nx, ny = max(0, bx - 22), max(0, top + by - 22)
        boxes.append(f'<div class="hl-num" style="left:{nx:.1f}px;top:{ny:.1f}px;background:{accent}">{number}</div>')
    return (
        f'<div class="imgbox" style="width:{box_w}px;height:{box_h}px">'
        f'<div class="clip" style="left:{left:.1f}px;top:{top:.1f}px;width:{shown_w:.1f}px;height:{shown_h:.1f}px">'
        f'<img src="{uri}" style="width:{shown_w:.1f}px;height:{full_h:.1f}px;top:{offset:.1f}px">'
        + "".join(masks) + "</div>"
        + "".join(boxes)
        + "</div>"
    )


IMG_CSS = """
.imgbox { position: relative; flex: none; }
.clip { position: absolute; overflow: hidden; border-radius: 18px; box-shadow: 0 6px 28px rgba(0,0,0,.14); background: #fff; }
.clip img { position: absolute; left: 0; display: block; }
.privacy-mask { position: absolute; z-index: 2; background: #151515; }
.hl { position: absolute; border: 8px solid; border-radius: 12px; box-shadow: 0 0 0 4px rgba(255,255,255,.7); }
.hl-num { position: absolute; width: 48px; height: 48px; border-radius: 50%; color: #fff; font-size: 30px; font-weight: 900; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 0 4px #fff; }
.legend-notes { display: flex; flex-wrap: wrap; gap: 14px 18px; margin-top: 22px; }
.legend-note { display: flex; align-items: center; gap: 12px; font-size: 32px; font-weight: 800; }
.legend-note i { font-style: normal; width: 44px; height: 44px; border-radius: 50%; color: #fff; display: inline-flex; align-items: center; justify-content: center; font-size: 28px; }
"""


def box_notes(highlights: Optional[Dict[str, Any]]) -> List[str]:
    notes = []
    for item in (highlights or {}).get("boxes", []) or []:
        if all(k in item for k in ("x", "y", "w", "h")):
            notes.append(str(item.get("note") or ""))
    return notes


def legend_html(notes: List[str], accent: str) -> str:
    shown = [(index, note) for index, note in enumerate(notes, 1) if note]
    if not shown:
        return ""
    return '<div class="legend-notes">' + "".join(f'<span class="legend-note"><i style="background:{accent}">{index}</i>{esc(note)}</span>' for index, note in shown) + "</div>"


def evidence_html(p: Dict[str, str], *, tool_name: str, meta: str, label: str, image: Optional[Path], highlights: Optional[Dict[str, Any]], **common: Any) -> str:
    notes = [note for note in box_notes(highlights) if note]
    box_w = W - 128
    box_h = 1440 - (130 if common["draft"] else 80) - 64 - 200 - 120 - (70 * math.ceil(len(notes) / 2) if notes else 0)
    css = IMG_CSS + f"""
.toolbar {{ display: flex; align-items: center; gap: 22px; margin-bottom: 26px; }}
.toolchip {{ background: {p['ink']}; color: {p['bg']}; font-size: 46px; font-weight: 900; padding: 10px 28px; border-radius: 14px; }}
.meta {{ font-size: 28px; color: {p['muted']}; line-height: 1.35; }}
.title {{ font-size: 54px; margin-bottom: 24px; }}
"""
    content = f"""<div class="toolbar"><span class="meta">{esc(meta)}</span></div>
{_image_box(image, box_w, box_h, highlights, p['warn'], '待录入截图')}{legend_html(box_notes(highlights) if image else [], p['warn'])}"""
    title = label.replace("各AI", tool_name).replace("各工具", tool_name)
    return inner_page(p, eyebrow=common["eyebrow"], title=title, content=content, footer_left=common["footer"], page_label=common["page"], draft=common["draft"], css=css)


def grid_html(p: Dict[str, str], *, label: str, cells: List[Dict[str, Any]], **common: Any) -> str:
    count = max(1, len(cells))
    cols = 1 if count == 1 else 2
    rows = math.ceil(count / cols)
    area_w = W - 128
    area_h = 1440 - (130 if common["draft"] else 80) - 64 - 200 - 120
    gap = 24
    cell_w = int((area_w - gap * (cols - 1)) / cols)
    cell_h = int((area_h - gap * (rows - 1)) / rows) - 58
    css = IMG_CSS + f"""
.grid {{ display: grid; grid-template-columns: repeat({cols}, {cell_w}px); gap: {gap}px; }}
.cell-label {{ font-size: 34px; font-weight: 900; margin-bottom: 12px; height: 46px; }}
.title {{ font-size: 54px; margin-bottom: 24px; }}
"""
    parts = []
    for cell in cells:
        parts.append(
            f'<div><div class="cell-label">{esc(cell.get("name", ""))}</div>'
            + _image_box(cell.get("image"), cell_w, cell_h, cell.get("highlights"), p["warn"], "待录入")
            + "</div>"
        )
    content = f'<div class="grid">{"".join(parts)}</div>'
    return inner_page(p, eyebrow=common["eyebrow"], title=label, content=content, footer_left=common["footer"], page_label=common["page"], draft=common["draft"], css=css)


# ---------------------------------------------------------------- score & text
def _cell(check: Dict[str, Any], value: Any) -> str:
    kind = check.get("type", "boolean")
    if value in (None, "", "pending"):
        return '<span class="pending">—</span>'
    if kind == "boolean":
        return '<span class="ok">✓</span>' if value == "pass" else '<span class="bad">✗</span>'
    text = str(value)
    return f'<span class="txt">{esc(text if len(text) <= 10 else text[:9] + "…")}</span>'


def scorecard_html(p: Dict[str, str], *, label: str, tools: List[Dict[str, Any]], checks: Dict[str, Any], overall_label: str, note: str, **common: Any) -> str:
    visible = list(checks.items())[:7]
    cols = len(visible) + 1
    name_w = 230
    col_w = int((W - 128 - name_w) / max(cols, 1))
    head_font = 26 if cols > 5 else 30
    css = f"""
.table {{ background: {p['surface']}; border-radius: 26px; overflow: hidden; }}
.tr {{ display: grid; grid-template-columns: {name_w}px repeat({cols}, {col_w}px); align-items: center; border-bottom: 2px solid {p['line']}; }}
.tr:last-child {{ border-bottom: 0; }}
.th {{ background: {p['accent_soft']}; font-size: {head_font}px; font-weight: 800; color: {p['ink']}; min-height: 124px; }}
.th div, .td div {{ padding: 14px 10px; text-align: center; line-height: 1.3; }}
.th div:first-child, .td div:first-child {{ text-align: left; padding-left: 28px; }}
.td {{ min-height: 116px; font-size: 36px; font-weight: 800; }}
.ok {{ color: {p['accent']}; font-size: 52px; }}
.bad {{ color: {p['warn']}; font-size: 52px; }}
.pending {{ color: {p['muted']}; }}
.txt {{ font-size: 28px; font-weight: 700; }}
.score {{ font-size: 46px; font-weight: 900; }}
.legend {{ display: flex; gap: 36px; font-size: 30px; color: {p['muted']}; margin-top: 26px; }}
"""
    header = "".join(f"<div>{esc(check.get('name', check_id))}</div>" for check_id, check in visible)
    rows = []
    for tool in tools:
        result = tool.get("result") or {}
        values = result.get("checks") or {}
        cells = "".join(f"<div>{_cell(check, values.get(check_id))}</div>" for check_id, check in visible)
        score = result.get("total_score")
        score_html = f'<span class="score">{esc(score)}</span>' if score is not None else '<span class="pending">—</span>'
        rows.append(f'<div class="tr td"><div>{esc(tool["name"])}</div>{cells}<div>{score_html}</div></div>')
    content = f"""<div class="table"><div class="tr th"><div>工具</div>{header}<div>{esc(overall_label)}</div></div>{''.join(rows)}</div>
<div class="legend"><span>✓ 通过</span><span>✗ 踩坑</span><span>— 待评</span></div>
<div class="note">{esc(note)}</div>"""
    return inner_page(p, eyebrow=common["eyebrow"], title=label, content=content, footer_left=common["footer"], page_label=common["page"], draft=common["draft"], css=css)


def conclusion_html(p: Dict[str, str], *, label: str, tools: List[Dict[str, Any]], overall_label: str, closer: str, **common: Any) -> str:
    def rank(tool: Dict[str, Any]) -> float:
        score = (tool.get("result") or {}).get("total_score")
        return -float(score) if isinstance(score, (int, float)) else 1.0

    count = max(1, len(tools))
    compact = count >= 5
    pad, name_px, score_px, verdict_px, gap, clamp = (20, 40, 48, 30, 14, 1) if compact else (30, 46, 58, 34, 20, 2)
    items = []
    for tool in sorted(tools, key=rank):
        result = tool.get("result") or {}
        score = result.get("total_score")
        verdict = result.get("verdict") or "待实测"
        # “我的结论” page speaks in your own words: your gut reaction first, the summary as fallback.
        gut = str(result.get("gut_reaction") or "").strip()
        line = f"“{gut}”" if gut else (result.get("summary") or "")
        items.append(
            f'<div class="item"><div class="line1"><span class="name">{esc(tool["name"])}</span>'
            f'<span class="verdict">{esc(verdict)}</span>'
            f'<span class="score">{esc(score if score is not None else "—")}<small>/5</small></span></div>'
            + (f'<div class="summary{" gut" if gut else ""}">{esc(line)}</div>' if line else "")
            + "</div>"
        )
    css = f"""
.list {{ display: flex; flex-direction: column; gap: {gap}px; flex: 1; min-height: 0; overflow: hidden; }}
.item {{ flex: none; background: {p['surface']}; border-radius: 22px; padding: {pad}px 32px; }}
.line1 {{ display: flex; align-items: baseline; gap: 22px; }}
.name {{ font-size: {name_px}px; font-weight: 900; white-space: nowrap; }}
.verdict {{ flex: 1; font-size: {verdict_px}px; font-weight: 800; color: {p['ink']}; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}
.score {{ font-size: {score_px}px; font-weight: 900; color: {p['accent']}; white-space: nowrap; }}
.score small {{ font-size: 28px; color: {p['muted']}; }}
.summary {{ font-size: {verdict_px - 3}px; color: {p['muted']}; margin-top: 6px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: {clamp}; -webkit-box-orient: vertical; overflow: hidden; }}
.summary.gut {{ color: {p['ink']}; font-weight: 700; }}
.closer {{ font-size: 38px; font-weight: 900; margin-top: 22px; flex: none; }}
.sub {{ font-size: 30px; color: {p['muted']}; margin-bottom: 18px; flex: none; }}
"""
    content = f'<div class="sub">{esc(overall_label)}</div><div class="list">{"".join(items)}</div><div class="closer">{esc(closer)}</div>'
    return inner_page(p, eyebrow=common["eyebrow"], title=label, content=content, footer_left=common["footer"], page_label=common["page"], draft=common["draft"], css=css)


def text_card_html(p: Dict[str, str], *, card: Dict[str, Any], label: str, **common: Any) -> str:
    lines = [str(line) for line in card.get("lines", [])] or ["待填写"]
    longest = max(text_width(line) for line in lines)
    font = int(max(30, min(46, 900 / max(longest, 1) * 1.9, 980 / (len(lines) * 1.9))))
    css = f"""
.lines {{ display: flex; flex-direction: column; gap: 20px; }}
.ln {{ background: {p['surface']}; border-radius: 20px; padding: 26px 32px; font-size: {font}px; font-weight: 700; line-height: 1.42; word-break: break-all; }}
"""
    content = '<div class="lines">' + "".join(f'<div class="ln">{esc(line)}</div>' for line in lines) + "</div>"
    return inner_page(p, eyebrow=common["eyebrow"], title=card.get("title") or label, content=content, footer_left=common["footer"], page_label=common["page"], draft=common["draft"], css=css)


def photo_html(p: Dict[str, str], *, image: Optional[Path], caption: str, draft: bool, page_label: str) -> str:
    uri = data_uri(image)
    photo = f'<img class="ph" src="{uri}">' if uri else '<div class="ph empty">待放入照片（photos/ 文件夹）</div>'
    css = f"""
.ph {{ position: absolute; inset: 0; width: {W}px; height: {H}px; object-fit: cover; }}
.empty {{ display: flex; align-items: center; justify-content: center; font-size: 52px; font-weight: 800; color: {p['muted']}; background: {p['line']}; }}
.cap {{ position: absolute; left: 0; right: 0; bottom: 0; padding: 60px 64px 56px; background: linear-gradient(transparent, rgba(0,0,0,.72)); color: #fff; font-size: 50px; font-weight: 900; line-height: 1.35; }}
.pg {{ position: absolute; right: 40px; top: {100 if draft else 36}px; color: #fff; font-size: 28px; background: rgba(0,0,0,.4); padding: 6px 16px; border-radius: 10px; }}
"""
    body = f'{photo}{draft_marks(draft)}<div class="pg">{esc(page_label)}</div><div class="cap">{esc(caption)}</div>'
    return page(body, bg="#000", ink="#fff", extra_css=css, title=caption)
