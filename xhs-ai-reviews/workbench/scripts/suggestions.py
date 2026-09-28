"""Claude's suggested judgments for a post (posts/<id>/suggestions.json).

Claude (Opus 5.5, in Cowork) reads the screenshots and answers, then writes
suggestions here through ``scripts/xhs.py suggest``. They never count as
results on their own: the workbench shows them next to each check, you accept
or change them, and only the accepted values go into scorecard.json. Your own
one-line reaction (gut_reaction) is never suggested.
"""
from __future__ import annotations

from typing import Any, Dict

try:
    from scripts.project import Project, ProjectError, load_json, now_iso, write_json
except ImportError:  # pragma: no cover
    from project import Project, ProjectError, load_json, now_iso, write_json  # type: ignore

MAX_TEXT = 400


def suggestions_path(project: Project, post_id: str):
    return project.post_dir(post_id) / "suggestions.json"


def load_suggestions(project: Project, post_id: str) -> Dict[str, Any]:
    data = load_json(suggestions_path(project, post_id), {}) or {}
    data.setdefault("tools", {})
    return data


def _text(value: Any, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ProjectError(f"{label} 需为文字")
    if len(value) > MAX_TEXT:
        raise ProjectError(f"{label} 超过 {MAX_TEXT} 字")
    return value.strip()


def _value_ok(check: Dict[str, Any], value: Any) -> bool:
    kind = check.get("type", "boolean")
    if kind == "boolean":
        return value in ("pass", "fail", "unclear")
    if kind == "enum":
        return value in (check.get("options") or [])
    if kind == "number":
        if type(value) not in (int, float):
            return False
        return check.get("min", float("-inf")) <= value <= check.get("max", float("inf"))
    return isinstance(value, str) and bool(value.strip())


def _squash(text: str) -> str:
    return "".join(str(text).split())


def _tool_texts(project: Project, post_id: str, tool: str) -> str:
    """Only this tool's transcribed answers may support a suggested quote."""
    manifest = load_json(project.post_dir(post_id) / "evidence" / "manifest.json", {}) or {}
    files = ((manifest.get("tools") or {}).get(tool) or {}).get("files") or {}
    chunks = []
    base = project.post_dir(post_id) / "evidence" / tool
    for relative in files.values():
        try:
            path = project.resolve_inside(relative, base)
        except ProjectError:
            continue
        if path.parent == base.resolve() and path.suffix.lower() == ".txt" and path.is_file():
            try:
                chunks.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                continue
    return _squash("\n".join(chunks))


def save_suggestions(project: Project, post_id: str, payload: Any, *, merge: bool = True) -> Dict[str, Any]:
    """Validate and store suggestions. ``unclear`` means “look yourself”."""
    if not isinstance(payload, dict) or not isinstance(payload.get("tools"), dict):
        raise ProjectError("建议格式应为 {\"tools\": {工具: {...}}}")
    scorecard = load_json(project.post_dir(post_id) / "scorecard.json", {}) or {}
    checks = scorecard.get("checks") or {}
    tools = project.post_tools(post_id)
    current = load_suggestions(project, post_id) if merge else {"tools": {}}
    for tool, entry in payload["tools"].items():
        if tool not in tools:
            raise ProjectError(f"这一篇没有这个工具：{tool}")
        if not isinstance(entry, dict):
            raise ProjectError(f"{tool} 的建议格式无效")
        if "gut_reaction" in entry or "keep_using" in entry:
            raise ProjectError("真实感受只能由你本人填写，Claude 不提供建议")
        target = current["tools"].setdefault(tool, {"checks": {}})
        texts = None
        for check_id, item in (entry.get("checks") or {}).items():
            if check_id not in checks:
                raise ProjectError(f"没有这个检查项：{check_id}")
            if not isinstance(item, dict) or not _value_ok(checks[check_id], item.get("value")):
                raise ProjectError(f"{tool} / {check_id} 的建议值无效")
            target["checks"][check_id] = {
                "value": item["value"],
                "quote": _text(item.get("quote"), "引用原句"),
                "reason": _text(item.get("reason"), "理由"),
            }
            if checks[check_id].get("type", "boolean") == "boolean" and item["value"] != "unclear" and not target["checks"][check_id]["reason"]:
                raise ProjectError(f"{tool} / {check_id}：通过或踩坑的建议需要写理由")
            quote = target["checks"][check_id]["quote"]
            if quote:
                if texts is None:
                    texts = _tool_texts(project, post_id, tool)
                if not texts:
                    raise ProjectError(f"{tool} / {check_id}：没有可核对的转写原文，不能引用原句")
                if _squash(quote) not in texts:
                    raise ProjectError(f"{tool} / {check_id}：引用的原句在本工具转写原文里找不到（“{quote[:20]}”），请逐字引用")
        score = entry.get("total_score")
        if score is not None:
            if type(score) not in (int, float) or not 1 <= score <= 5:
                raise ProjectError("建议总分需在 1–5 之间")
            target["total_score"] = score
        for key, label in (("verdict", "结论"), ("summary", "一句话结论")):
            if key in entry:
                target[key] = _text(entry[key], label)
    if "note" in payload:
        current["note"] = _text(payload["note"], "说明")
    current["generated_by"] = _text(payload.get("generated_by") or current.get("generated_by") or "Claude (Opus 5.5)", "来源")
    current["generated_at"] = now_iso()
    write_json(suggestions_path(project, post_id), current)
    return current


def note_for(item: Dict[str, Any]) -> str:
    """The evidence note written into the scorecard when a suggestion is accepted."""
    prefix = {"pass": "通过", "fail": "踩坑"}.get(item.get("value"), "待定")
    parts = [f"{prefix}：{item.get('reason') or ''}".rstrip("：")]
    if item.get("quote"):
        parts.append(f"原文“{item['quote']}”")
    return "｜".join(parts)
