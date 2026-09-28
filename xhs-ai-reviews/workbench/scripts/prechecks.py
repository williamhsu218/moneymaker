#!/usr/bin/env python3
"""Assistive pre-checks on raw answers: highlight, never decide.

Each topic lists its pre-checks in harness/topics.json. Results are shown next
to the human scoring form; they are never written into the scorecard.

    python scripts/prechecks.py post-01-weekly-report
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

from scripts.project import Project, load_json

FULLWIDTH = str.maketrans("０１２３４５６７８９．％", "0123456789.%")
KEYCAP_RE = re.compile(r"[0-9#*]️?⃣")
LIST_MARKER_RE = re.compile(r"(?m)^\s*(?:\d{1,2}[.、)）]|[（(]\d{1,2}[)）])")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")
MARKDOWN_RE = re.compile(r"[*_#>`]")


def _snippet(text: str, start: int, end: int, radius: int = 14) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return ("…" if left else "") + text[left:right].replace("\n", " ") + ("…" if right < len(text) else "")


def normalize(text: str) -> str:
    return KEYCAP_RE.sub("", str(text or "")).translate(FULLWIDTH)


def numbers_in(text: str, *, skip_list_markers: bool = True) -> List[re.Match]:
    cleaned = normalize(text)
    if skip_list_markers:
        cleaned = LIST_MARKER_RE.sub(lambda match: " " * len(match.group(0)), cleaned)
    return list(NUMBER_RE.finditer(cleaned))


CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_to_int(text: str) -> Optional[int]:
    """Small Chinese numerals (up to 999) such as 三, 十一, 一百五十."""
    if not text or any(ch not in CN_DIGITS and ch not in "十百" for ch in text):
        return None
    total, current = 0, 0
    for ch in text:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
    return total + current


def check_new_numbers(texts: Dict[str, str], source: str) -> Dict[str, Any]:
    allowed = {match.group(0).rstrip("%") for match in numbers_in(source, skip_list_markers=False)}
    for run in re.findall(r"[零一二两三四五六七八九十百]+", source):
        for size in range(1, len(run) + 1):
            for start in range(0, len(run) - size + 1):
                value = cn_to_int(run[start:start + size])
                if value is not None:
                    allowed.add(str(value))
    hits = []
    for key, text in texts.items():
        cleaned = normalize(text)
        cleaned = LIST_MARKER_RE.sub(lambda match: " " * len(match.group(0)), cleaned)
        for match in NUMBER_RE.finditer(cleaned):
            value = match.group(0)
            if value.rstrip("%") in allowed:
                continue
            hits.append({"key": key, "match": value, "context": _snippet(cleaned, match.start(), match.end())})
    return {"status": "flag" if hits else "ok", "hits": hits[:12], "detail": f"{len(hits)} 处输入里没有的数字" if hits else "没有发现输入里没有的数字"}


NEGATION_RE = re.compile(r"[未没不无]")


def _negated(text: str, start: int) -> bool:
    """True for “尚未修复完成”“还没解决”“未能修复完成”: a negation just before the word."""
    return bool(NEGATION_RE.search(text[max(0, start - 2):start]))


def check_keywords(texts: Dict[str, str], words: List[str]) -> Dict[str, Any]:
    hits, negated = [], []
    for key, text in texts.items():
        lowered = str(text).lower()
        for word in words:
            start = lowered.find(word.lower())
            while start != -1:
                if _negated(lowered, start):
                    negated.append({"key": key, "match": str(text)[max(0, start - 2):start + len(word)]})
                else:
                    hits.append({"key": key, "match": word, "context": _snippet(str(text), start, start + len(word))})
                start = lowered.find(word.lower(), start + len(word))
    detail = "出现：" + "、".join(sorted({hit["match"] for hit in hits})) if hits else "没有出现"
    if negated:
        detail += f"（另有 {len(negated)} 处是否定说法，如“{negated[0]['match']}”，已忽略）"
    return {"status": "flag" if hits else "ok", "hits": hits[:12], "negated": negated[:6], "detail": detail}


def count_chars(text: str) -> Dict[str, int]:
    stripped = str(text or "").strip()
    no_space = re.sub(r"\s", "", stripped)
    no_markdown = MARKDOWN_RE.sub("", no_space)
    return {"with_spaces": len(stripped), "without_spaces": len(no_space), "without_markdown": len(no_markdown)}


def check_char_count(text: str, maximum: int) -> Dict[str, Any]:
    counts = count_chars(text)
    over = counts["with_spaces"] > maximum
    detail = f"{counts['with_spaces']} 字（含标点和空格）；去掉空白 {counts['without_spaces']}；再去掉 Markdown 符号 {counts['without_markdown']}；上限 {maximum}"
    return {"status": "flag" if over else "ok", "counts": counts, "detail": detail, "hits": []}


def _section_after(text: str, markers: List[str]):
    """(marker, text after its last occurrence) for the latest marker, e.g. the “下周计划” part."""
    best, found = -1, None
    for marker in markers:
        position = text.rfind(marker)
        if position != -1 and position + len(marker) > best:
            best, found = position + len(marker), marker
    return (found.rstrip("：:"), text[best:]) if found else (None, None)


def check_must_include(text: str, groups: List[List[str]], after: Optional[List[str]] = None) -> Dict[str, Any]:
    scope = str(text)
    note = ""
    if after:
        marker, section = _section_after(scope, after)
        if section is None:
            note = f"（没找到“{after[0]}”这一段，按全文查）"
        else:
            scope = section
            note = f"（只看“{marker}”之后的部分）"
    missing = [group for group in groups if not any(word.lower() in scope.lower() for word in group)]
    detail = ("都出现了" if not missing else "没找到：" + "；".join("/".join(group) for group in missing)) + note
    return {"status": "flag" if missing else "ok", "missing": missing, "detail": detail, "hits": []}


def check_regex(texts: Any, pattern: str) -> Dict[str, Any]:
    if isinstance(texts, str):
        texts = {"text": texts}
    hits = [
        {"key": key, "match": match.group(0), "context": _snippet(str(text), match.start(), match.end())}
        for key, text in texts.items()
        for match in re.finditer(pattern, str(text))
    ]
    return {"status": "flag" if hits else "ok", "hits": hits[:12], "detail": "出现：" + "、".join(sorted({hit["match"] for hit in hits})) if hits else "没有出现"}


def _read_text(project: Project, relative: Optional[str]) -> Optional[str]:
    if not relative:
        return None
    path = project.root / relative
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def run_prechecks(project: Project, post_id: str) -> Dict[str, Any]:
    topic = project.post_topic(post_id)
    manifest = load_json(project.post_dir(post_id) / "evidence" / "manifest.json", {}) or {}
    tests = {test.get("id"): test.get("text", "") for test in topic.get("tests", [])}
    results: Dict[str, List[Dict[str, Any]]] = {}
    for tool in project.post_tools(post_id):
        files = ((manifest.get("tools") or {}).get(tool) or {}).get("files") or {}
        tool_results = []
        for spec in topic.get("prechecks", []):
            kind = spec.get("type")
            keys = spec.get("keys") or ([spec["key"]] if spec.get("key") else [])
            texts = {key: _read_text(project, files.get(key)) for key in keys}
            available = {key: value for key, value in texts.items() if value is not None}
            base = {"label": spec.get("label", kind), "type": kind, "check": spec.get("check")}
            if not available:
                tool_results.append({**base, "status": "missing", "detail": "还没有录入回答原文", "hits": []})
                continue
            if kind == "new_numbers":
                sources = spec.get("source_tests") or [spec.get("source_test")]
                source = "\n".join(tests.get(test_id, "") for test_id in sources if test_id)
                outcome = check_new_numbers(available, source)
            elif kind == "keywords":
                outcome = check_keywords(available, spec.get("words", []))
            elif kind == "char_count":
                outcome = check_char_count(next(iter(available.values())), int(spec.get("max", 0)))
            elif kind == "must_include":
                outcome = check_must_include(next(iter(available.values())), spec.get("groups", []), spec.get("after"))
            elif kind == "regex":
                outcome = check_regex(available, spec.get("pattern", "$^"))
            else:
                outcome = {"status": "missing", "detail": f"未知的预检类型 {kind}", "hits": []}
            tool_results.append({**base, **outcome})
        results[tool] = tool_results
    return {"post_id": post_id, "note": "仅供参考：高亮可疑处，是否踩坑以你对照原文的判断为准。", "results": results}


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法：python scripts/prechecks.py <post_id>", file=sys.stderr)
        return 2
    report = run_prechecks(Project(), args[0])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
