"""Map a lead to one of the 12 topics in harness/topics.json.

Keywords live here; tools, titles and cover drafts come from topics.json so
there is only one place to change them. Unknown or unverifiable signals stay
“unmatched” for human review.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

try:
    from scripts.project import Project
except ImportError:  # pragma: no cover
    from project import Project  # type: ignore

logger = logging.getLogger("topic_matcher")

KEYWORDS: Dict[str, List[str]] = {
    "01": ["周报", "汇报", "日报", "工作记录", "瞎编", "weekly_report"],
    "02": ["ppt", "幻灯片", "演示文稿", "presentation", "slide", "keynote", "智文", "aippt"],
    "03": ["数学", "奥数", "算术", "解题", "应用题", "math", "思维题", "小学", "做作业", "辅导"],
    "04": ["翻译", "英文", "英语", "translation", "translate", "bilingual", "中英"],
    "05": ["excel", "表格", "公式", "函数", "vlookup", "xlookup", "spreadsheet", "wps表格"],
    "06": ["论文", "文献", "长文档", "pdf", "研报", "学术", "paper", "综述"],
    "07": ["会议", "录音", "纪要", "语音转文字", "meeting", "听悟", "妙记", "转写", "说话人"],
    "08": ["旅游", "攻略", "出行", "行程", "路线规划", "travel", "itinerary", "景点"],
    "09": ["修图", "消除", "抠图", "扩图", "照片", "photo", "人像", "证件照", "美图"],
    "10": ["拍视频", "视频生成", "文生视频", "图生视频", "video generation", "可灵", "即梦", "海螺", "kling"],
    "11": ["新品", "新模型", "新功能", "正式发布", "版本更新", "更新到", "release", "launch", "多模态", "视频理解"],
    "12": ["合集", "盘点", "recap", "roundup", "复盘", "年度精选"],
}
VIDEO_UNDERSTANDING = ["看视频", "看懂视频", "视频理解", "多模态", "multimodal", "长视频"]
VIDEO_GENERATION = ["拍视频", "视频生成", "文生视频", "图生视频", "video generation", "sora", "kling"]


def _score(keywords: List[str], text: str) -> Tuple[int, List[str]]:
    score, matched = 0, []
    for keyword in keywords:
        lowered = keyword.lower()
        if keyword.isascii() and re.search(r"[a-zA-Z]", keyword):
            hit = re.search(rf"\b{re.escape(lowered)}\b", text, flags=re.ASCII) is not None
        else:
            hit = lowered in text
        if hit:
            matched.append(keyword)
            score += len(keyword) + 2
    return score, matched


def _unmatched(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic_id": "unmatched",
        "topic_name": "待人工匹配",
        "hook_title": "线索待核实，尚未对应测试题",
        "prompt_file": None,
        "comparison_group": [],
        "cover_layout": {"top_tag": "待人工匹配", "main_title": "线索待核实", "subtitle": "先查来源与可用性", "tool_tags": []},
        "matched_keywords": [],
        "requires_manual_review": True,
        "raw_event": event,
    }


def match_topic_and_generate_card(event_data: Dict[str, Any], project: Optional[Project] = None) -> Dict[str, Any]:
    project = project or Project()
    text = " ".join(str(event_data.get(key, "")) for key in ("category", "title", "description", "source")).lower()
    if "arena_anonymous" in text:
        return _unmatched(event_data)
    understands = any(signal in text for signal in VIDEO_UNDERSTANDING)
    generates = any(signal in text for signal in VIDEO_GENERATION)
    best, best_score, best_matched = None, 0, []
    for topic_id, keywords in KEYWORDS.items():
        if topic_id == "10" and understands and not generates:
            continue
        if topic_id == "11" and generates and not understands:
            continue
        score, matched = _score(keywords, text)
        if score > best_score:
            best, best_score, best_matched = topic_id, score, matched
    if not best:
        return _unmatched(event_data)
    try:
        topic = project.topic(best)
    except ValueError:
        return _unmatched(event_data)
    title = str(event_data.get("custom_title") or event_data.get("hook_title") or topic.get("title", "")).strip()
    if not 1 <= len(title) <= 20:
        logger.warning("Title %r is not 1-20 characters; using the topic title", title)
        title = topic.get("title", "")
    cover = topic.get("cover") or {}
    lines = cover.get("lines") or []
    return {
        "topic_id": best,
        "topic_name": topic.get("name", ""),
        "hook_title": title,
        "prompt_file": topic.get("prompt_file"),
        "comparison_group": [project.tool_name(tool) for tool in topic.get("tools", [])],
        "cover_layout": {"top_tag": cover.get("tag", ""), "main_title": lines[0] if lines else "", "subtitle": " ".join(lines[1:]), "tool_tags": [project.tool_name(tool) for tool in topic.get("tools", [])]},
        "matched_keywords": best_matched,
        "requires_manual_review": True,
        "raw_event": event_data,
    }
