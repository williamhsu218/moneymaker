"""Who does the next step on a post — you or Claude (Opus 5.5 in Cowork).

The workbench and ``scripts/xhs.py status`` both use this, so they always show
the same next action and the same sentence to say to Claude.
"""
from __future__ import annotations

from typing import Dict

try:
    from scripts.evidence_intake import list_inbox
    from scripts.ops import load_calendar
    from scripts.project import Project, load_json
    from scripts.readiness import assess_post_readiness, evidence_status
    from scripts.suggestions import load_suggestions
except ImportError:  # pragma: no cover
    from evidence_intake import list_inbox  # type: ignore
    from ops import load_calendar  # type: ignore
    from project import Project, load_json  # type: ignore
    from readiness import assess_post_readiness, evidence_status  # type: ignore
    from suggestions import load_suggestions  # type: ignore

PHRASES = {
    "intake": "第{id}期截图放好了",
    "draft": "第{id}期确认好了",
    "final": "第{id}期复核好了",
}


def next_step(project: Project, post_id: str) -> Dict[str, str]:
    """Who acts next on this post.

    ``say`` is the sentence to send Claude now (Claude's turn); ``then`` is the
    sentence to send Claude once you have finished your part (your turn).
    """
    topic_id = project.load_post(post_id)["topic_id"]
    for week in load_calendar(project).get("weeks", []):
        if any(slot.get("post_id") == post_id and slot.get("status") == "已发布" for slot in week.get("slots", [])):
            return {"owner": "你", "action": "这篇已发布；按 24h、72h、7d 回填数据并查看复盘"}
    readiness = assess_post_readiness(project, post_id)
    codes = {item["code"] for item in readiness["blockers"]}
    evidence = evidence_status(project, post_id)
    inbox = list_inbox(project, post_id)
    suggestions = load_suggestions(project, post_id)
    scorecard = load_json(project.post_dir(post_id) / "scorecard.json", {}) or {}
    reactions = [tool for tool, result in (scorecard.get("tool_results") or {}).items() if not (result or {}).get("gut_reaction")]
    if readiness["publishable"]:
        return {"owner": "你", "action": "复制发布包去 App 发布，发完回来标记已发布、第二天回填数据"}
    if "evidence_incomplete" in codes:
        if inbox:
            return {"owner": "Claude", "action": f"整理 inbox 里的 {len(inbox)} 个文件", "say": PHRASES["intake"].format(id=topic_id)}
        return {"owner": "你", "action": f"在 App 里测试并截图，AirDrop 到 posts/{post_id}/inbox/（证据 {evidence['count']}/{evidence['required_count']}）"}
    if "scoring_incomplete" in codes:
        if not suggestions.get("tools"):
            return {"owner": "Claude", "action": "给出判定建议和初稿", "say": PHRASES["intake"].format(id=topic_id)}
        then = PHRASES["draft"].format(id=topic_id)
        if reactions:
            return {"owner": "你", "action": f"在工作台“确认判定”里采纳或修改建议，并写下对 {len(reactions)} 个工具的真实感受", "then": then}
        return {"owner": "你", "action": "在工作台“确认判定”里把剩下的检查项定下来并保存", "then": then}
    if "copy_blocked" in codes or "cards_placeholder" in codes:
        return {"owner": "Claude", "action": "用你确认的结果和感受写定稿", "say": PHRASES["draft"].format(id=topic_id)}
    if codes & {"scorecard_draft", "review_pending", "review_stale"}:
        return {"owner": "你", "action": "在工作台“复核”里逐条核对后点一次复核", "then": PHRASES["final"].format(id=topic_id)}
    if "assets_stale" in codes:
        return {"owner": "Claude", "action": "生成终版图片并检查发布包", "say": PHRASES["final"].format(id=topic_id)}
    return {"owner": "你", "action": readiness["blockers"][0]["message"] if readiness["blockers"] else "检查工作台"}

