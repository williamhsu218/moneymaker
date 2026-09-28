#!/usr/bin/env python3
"""Create a post workspace for one topic.

    python scripts/new_post.py 02                 # posts/post-02-ppt/
    python scripts/new_post.py 11 --slug qwen-omni --tools qianwen doubao
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.project import Project, ProjectError, POST_ID_RE, fill_brand_tokens, now_iso, write_json, write_text
from scripts.topic_docs import topic_markdown

COPY_CHECKLIST = [
    "正文每个判断都能在对应工具的原始回答和截图里找到",
    "标题、图片、评分卡和正文用的是同一版复核结果",
    "删除所有【】和没发生的“翻车”“首推”等说法",
    "发布页“内容类型声明”如实选择了 AI 辅助的选项",
    "截图里的个人信息已打码，照片和素材都有授权",
]


def copy_template(topic: Dict[str, Any], brand: Dict[str, Any]) -> str:
    lines = [
        f"# 第{topic['id']}期｜{topic.get('name', '')}｜笔记文案",
        "",
        "> 草稿：【】里填你实测出来的真实结果，填不出来说明还没测，不要编。第1个标题就是要用的标题。复核通过前，工作台不会放行发布包。",
        "",
        "## 标题候选",
        "",
    ]
    lines += [f"{index}. {title}" for index, title in enumerate(topic.get("titles", []), 1)]
    if topic.get("title_note"):
        lines += ["", f"> ⚠️ {topic['title_note']}"]
    lines += ["", "## 笔记正文", "", fill_brand_tokens(topic.get("body", ""), brand), "", "## 推荐标签", "", topic.get("tags", ""), "", "## 首评置顶", "", topic.get("pin", ""), "", "## 发布前核对", ""]
    lines += [f"- [ ] {item}" for item in COPY_CHECKLIST]
    if topic.get("extra"):
        lines += [f"- [ ] {topic['extra']}"]
    return "\n".join(lines) + "\n"


def blank_result() -> Dict[str, Any]:
    return {"checks": {}, "notes": {}, "total_score": None, "verdict": "", "summary": "", "gut_reaction": "", "keep_using": ""}


def blank_scorecard(post_id: str, topic: Dict[str, Any], tools: List[str]) -> Dict[str, Any]:
    return {
        "schema": 2,
        "post_id": post_id,
        "topic_id": topic["id"],
        "title": topic.get("name", ""),
        "status": "draft",
        "evaluator": None,
        "evaluation_date": None,
        "tools": list(tools),
        "checks": copy.deepcopy(topic.get("checks") or {}),
        "overall": copy.deepcopy(topic.get("overall") or {}),
        "tool_results": {tool: blank_result() for tool in tools},
    }


DEFAULT_PLATFORM = "手机 App"
DEFAULT_FREE_TIER = "免费版"


def blank_tool_entry(topic: Dict[str, Any]) -> Dict[str, Any]:
    """Protocol defaults are pre-filled; model, version and time come from the test."""
    return {
        "model": "", "version": "", "platform": DEFAULT_PLATFORM,
        "settings": topic.get("default_settings", ""), "free_tier": DEFAULT_FREE_TIER,
        "tested_at": "", "files": {}, "sources": {},
    }


def blank_manifest(tools: List[str], topic: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    topic = topic or {}
    return {
        "schema": 2,
        "status": "draft",
        "test_date": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "claims_reviewed": False,
        "tools": {tool: blank_tool_entry(topic) for tool in tools},
        "shared": {},
        "shared_sources": {},
        "reviewed_hashes": {},
    }


def create_post(
    project: Project,
    topic_id: str,
    *,
    tools: Optional[List[str]] = None,
    slug: Optional[str] = None,
    force: bool = False,
) -> str:
    topic = project.topic(topic_id)
    post_id = f"post-{topic['id']}-{slug or topic['slug']}"
    if not POST_ID_RE.match(post_id):
        raise ProjectError("slug 只能用小写字母、数字和连字符")
    post_dir = project.post_dir(post_id)
    if (post_dir / "post.json").exists() and not force:
        raise ProjectError(f"{post_id} 已存在")
    known = project.tool_map()
    chosen = list(tools) if tools else list(topic.get("tools", []))
    unknown = [tool for tool in chosen if tool not in known]
    if unknown:
        raise ProjectError(f"config/tools.json 里没有这些工具：{'、'.join(unknown)}")
    if len(set(chosen)) != len(chosen):
        raise ProjectError("参评工具有重复")
    if len(chosen) < int(topic.get("min_tools", 1)):
        raise ProjectError(f"这一期至少要 {topic.get('min_tools', 1)} 款工具")
    brand = project.brand()
    palette = (topic.get("cover") or {}).get("palette") or (brand.get("default_palette_by_format") or {}).get(topic.get("format"), "yellow")
    post = {
        "schema": 2,
        "post_id": post_id,
        "topic_id": topic["id"],
        "tools": chosen,
        "cover": {"tag": (topic.get("cover") or {}).get("tag", ""), "lines": list((topic.get("cover") or {}).get("lines", [])), "palette": palette},
        "variables": {},
        "picks": {},
        "created_at": now_iso(),
    }
    write_json(post_dir / "post.json", post)
    write_text(post_dir / "README.md", topic_markdown(topic, project, for_post=True, post_id=post_id))
    write_text(post_dir / "copy.md", copy_template(topic, brand))
    write_json(post_dir / "scorecard.json", blank_scorecard(post_id, topic, chosen))
    cards = copy.deepcopy(topic.get("cards") or {})
    cards["photo_captions"] = {}
    write_json(post_dir / "cards.json", cards)
    write_json(post_dir / "highlights.json", {})
    write_json(post_dir / "evidence" / "manifest.json", blank_manifest(chosen, topic))
    for folder in ("inbox", "images", "photos"):
        (post_dir / folder).mkdir(parents=True, exist_ok=True)
    return post_id


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="为一期选题建立工作区")
    parser.add_argument("topic_id", help="选题编号，如 02")
    parser.add_argument("--slug", help="目录名后缀，默认用选题自带的")
    parser.add_argument("--tools", nargs="+", help="参评工具 id（见 config/tools.json）")
    parser.add_argument("--force", action="store_true", help="覆盖已有工作区（会清空评分和证据清单）")
    args = parser.parse_args(argv)
    project = Project()
    try:
        post_id = create_post(project, args.topic_id.zfill(2), tools=args.tools, slug=args.slug, force=args.force)
        from scripts.ops import attach_post
        attach_post(project, args.topic_id.zfill(2), post_id)
    except ProjectError as exc:
        print(f"未创建：{exc}", file=sys.stderr)
        return 2
    print(f"已创建 posts/{post_id}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
