#!/usr/bin/env python3
"""Pre-publish checks for a post's copy.md.

Errors block the publish package (placeholders, off-platform contact, VPN
wording, over-long titles). Warnings are style nudges (length, tag count,
missing test conditions). Reminders are shown every time.

    python scripts/publish_lint.py post-01-weekly-report
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.project import Project

SECTION_ALIASES = {
    "titles": ("标题候选", "小红书标题候选", "标题"),
    "body": ("笔记正文", "正文"),
    "tags": ("推荐标签", "话题标签", "标签"),
    "pin": ("首评置顶", "置顶评论"),
    "checklist": ("发布前核对",),
}
PLACEHOLDER_RE = re.compile(r"【[^】]*】")
DRAFT_MARKERS = ("待实测", "禁止直接发布", "待填", "待核实", "请填写", "TODO")
OFF_PLATFORM = (
    "微信", "威信", "V信", "vx", "VX", "wx号", "加V", "加v", "二维码", "公众号", "视频号", "抖音", "快手",
    "B站", "b站", "哔哩哔哩", "微博", "知乎", "QQ群", "qq群", "QQ号", "淘宝店", "私信领取", "私我领",
)
LINK_RE = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|cn|net|io|ai|app)\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
VPN_WORDS = ("翻墙", "梯子", "VPN", "vpn", "科学上网", "魔法上网", "外网账号", "机场节点")
CONDITION_RE = re.compile(r"\d{1,2}月\d{1,2}日|20\d{2}[-/.年]\d{1,2}|免费版|测试时间|测试条件|测试当天")
REMINDERS = [
    "如实说明 AI 辅助参与；发布页若有“内容类型声明”，按实际创作过程选择",
    "发布动作由你在 App 内完成；不使用任何自动发布、自动评论或回复的脚本",
    "发布后 1 小时内发置顶评论，并回复评论（这是运营习惯，不是平台承诺的机制）",
    "第二天在创作者中心记下浏览、点赞、收藏、评论、分享、新增关注，回填到工作台",
]


def parse_copy(text: str) -> Dict[str, Any]:
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for raw in str(text).splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", raw)
        if heading:
            name = heading.group(1).strip()
            current = next((key for key, aliases in SECTION_ALIASES.items() if name in aliases), None)
            if current:
                sections.setdefault(current, [])
            continue
        if raw.startswith("# "):
            current = None
            continue
        if current and not raw.lstrip().startswith(">"):
            sections[current].append(raw)
    titles = []
    for line in sections.get("titles", []):
        match = re.match(r"^\s*(?:\d+[.、]|[-*])\s*(.+?)\s*$", line)
        if match:
            titles.append(match.group(1))
    checklist = []
    for line in sections.get("checklist", []):
        match = re.match(r"^\s*[-*]\s*\[( |x|X)\]\s*(.+)$", line)
        if match:
            checklist.append({"done": match.group(1).lower() == "x", "text": match.group(2).strip()})
    return {
        "titles": titles,
        "body": "\n".join(sections.get("body", [])).strip(),
        "tags": " ".join(line.strip() for line in sections.get("tags", []) if line.strip()),
        "pin": "\n".join(sections.get("pin", [])).strip(),
        "checklist": checklist,
        "has_sections": {key: key in sections for key in SECTION_ALIASES},
    }


def _hits(text: str, words) -> List[str]:
    return sorted({word for word in words if word in text})


def lint_copy(text: str, brand: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    brand = brand or {}
    parsed = parse_copy(text)
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    def error(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    def warn(code: str, message: str) -> None:
        warnings.append({"code": code, "message": message})

    titles, body, tags, pin = parsed["titles"], parsed["body"], parsed["tags"], parsed["pin"]
    title = titles[0] if titles else ""
    if not title:
        error("title_missing", "“标题候选”下没有标题（第1个标题就是要用的标题）")
    elif len(title) > 20:
        error("title_too_long", f"第1个标题 {len(title)} 字，超过 20 字：{title}")
    for index, extra in enumerate(titles[1:], 2):
        if len(extra) > 20:
            warn("alt_title_too_long", f"第{index}个备选标题 {len(extra)} 字，超过 20 字")
    if not body:
        error("body_missing", "“笔记正文”是空的")

    publish_text = {"标题": title, "正文": body, "标签": tags, "置顶评论": pin}
    for label, value in publish_text.items():
        placeholders = PLACEHOLDER_RE.findall(value)
        if placeholders:
            error("placeholder", f"{label}里还有 {len(placeholders)} 处【】待填：{'、'.join(placeholders[:3])}")
        markers = _hits(value, DRAFT_MARKERS)
        if markers:
            error("draft_marker", f"{label}里有草稿标记：{'、'.join(markers)}")
        off = _hits(value, OFF_PLATFORM)
        if off:
            error("off_platform", f"{label}里提到了站外平台或联系方式：{'、'.join(off)}（请按发布时平台规则核对）")
        if LINK_RE.search(value):
            error("link", f"{label}里有链接或网址（请按发布时平台规则核对）")
        if PHONE_RE.search(value):
            error("phone", f"{label}里有疑似手机号")
        vpn = _hits(value, VPN_WORDS)
        if vpn:
            error("vpn", f"{label}里有访问境外服务的说法：{'、'.join(vpn)}")

    body_len = len(body)
    if body and not 300 <= body_len <= 1000:
        warn("body_length", f"正文 {body_len} 字，建议 300–1000 字")
    tag_count = len(re.findall(r"#[^\s#]+", tags))
    if not 8 <= tag_count <= 10:
        warn("tag_count", f"标签 {tag_count} 个，建议 8–10 个")
    if brand.get("opener") and brand["opener"].rstrip("🍴").strip() not in body:
        warn("opener", "正文没有固定开场白（brand.json 的 opener）")
    closer_core = str(brand.get("closer", "")).replace("👇", "").strip()
    if closer_core and closer_core not in body:
        warn("closer", "正文没有固定结尾（评论区点菜）")
    if body and not CONDITION_RE.search(body + "\n" + pin):
        warn("conditions", "正文和置顶评论里没写测试日期或“免费版”等条件")
    if not pin:
        warn("pin_missing", "还没写置顶评论")
    open_items = [item["text"] for item in parsed["checklist"] if not item["done"]]
    if open_items:
        warn("checklist", f"“发布前核对”还有 {len(open_items)} 项没勾选")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "reminders": REMINDERS,
        "stats": {"title": title, "title_length": len(title), "body_length": body_len, "tag_count": tag_count},
        "parsed": parsed,
    }


def lint_cards(cards: Dict[str, Any]) -> List[Dict[str, str]]:
    """Text cards end up on images, so their placeholders block release too."""
    problems = []
    for card_id, card in (cards or {}).items():
        if card_id == "photo_captions" and isinstance(card, dict):
            for index, caption in card.items():
                if PLACEHOLDER_RE.search(str(caption)):
                    problems.append({"code": "card_placeholder", "message": f"照片{index}的说明里还有【】待填"})
            continue
        if not isinstance(card, dict):
            continue
        text = " ".join([str(card.get("title", ""))] + [str(line) for line in card.get("lines", [])])
        if PLACEHOLDER_RE.search(text):
            problems.append({"code": "card_placeholder", "message": f"文字卡“{card.get('title', card_id)}”里还有【】待填"})
    return problems


def lint_post(project: Project, post_id: str) -> Dict[str, Any]:
    post_dir = project.post_dir(post_id)
    try:
        text = (post_dir / "copy.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        text = ""
    report = lint_copy(text, project.brand())
    return report


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法：python scripts/publish_lint.py <post_id>", file=sys.stderr)
        return 2
    report = lint_post(Project(), args[0])
    report.pop("parsed", None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
