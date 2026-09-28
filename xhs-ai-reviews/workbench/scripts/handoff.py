#!/usr/bin/env python3
"""Build posts/<post_id>/handoff.md: everything Claude needs to draft copy.

In Cowork with this folder connected, say “第NN期可以写了” — Claude reads
handoff.md, then drafts copy.md, cards.json and highlights.json. Drafts still
go through the one-click review before anything is released.

    python scripts/handoff.py post-01-weekly-report
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prechecks import run_prechecks
from scripts.project import Project, load_json, write_text
from scripts.readiness import METADATA_FIELDS, METADATA_LABELS, assess_post_readiness, evidence_status

VALUE_NAMES = {"pass": "通过", "fail": "踩坑", "pending": "待评", None: "待评", "": "待评"}


def _value(check: Dict[str, Any], value: Any) -> str:
    if check.get("type", "boolean") == "boolean":
        return VALUE_NAMES.get(value, str(value))
    return "待评" if value in (None, "") else str(value)


def handoff_markdown(project: Project, post_id: str) -> str:
    post_dir = project.post_dir(post_id)
    topic = project.post_topic(post_id)
    brand = project.brand()
    scorecard = load_json(post_dir / "scorecard.json", {}) or {}
    manifest = load_json(post_dir / "evidence" / "manifest.json", {}) or {}
    readiness = assess_post_readiness(project, post_id, for_review=True)
    evidence = evidence_status(project, post_id, manifest)
    prechecks = run_prechecks(project, post_id)["results"]
    checks = scorecard.get("checks") or {}
    lines: List[str] = [
        f"# 交接包｜第{topic['id']}期 {topic.get('name', '')}（{post_id}）",
        "",
        "> 给 Claude：请按下面的真实结果起草。只写有证据支持的结论；没测到的不写；【】里填不出来就保留【】。",
        f"> 口吻：{brand.get('opener', '')} 开场，{brand.get('closer', '')} 结尾；短句、先说结论、不吹不黑。",
        "> 输出：更新本目录的 copy.md（保持现有小节结构）、cards.json 的文字卡、可选的 highlights.json 红框坐标（0–1 比例）。不要改 scorecard.json 和 evidence/。",
        "",
        "## 测试条件",
        "",
        topic.get("setup", ""),
        "",
        "## 各工具信息与结果",
        "",
    ]
    for tool in project.post_tools(post_id):
        entry = (manifest.get("tools") or {}).get(tool) or {}
        result = (scorecard.get("tool_results") or {}).get(tool) or {}
        lines.append(f"### {project.tool_name(tool)}")
        lines.append("")
        lines.append("- " + "；".join(f"{METADATA_LABELS[field]}：{entry.get(field) or '未填'}" for field in METADATA_FIELDS))
        for check_id, check in checks.items():
            note = (result.get("notes") or {}).get(check_id, "")
            lines.append(f"- {check.get('name', check_id)}：{_value(check, (result.get('checks') or {}).get(check_id))}{('｜依据：' + note) if note else ''}")
        overall = (scorecard.get("overall") or {}).get("label", "总评")
        lines.append(f"- {overall}：{result.get('total_score') if result.get('total_score') is not None else '待评'}")
        for key, label in (("verdict", "人工结论"), ("summary", "一句话结论"), ("gut_reaction", "第一反应（原话）"), ("keep_using", "会不会继续用")):
            if result.get(key):
                lines.append(f"- {label}：{result[key]}")
        flags = [item for item in prechecks.get(tool, []) if item.get("status") == "flag"]
        if flags:
            lines.append("- 预检高亮（仅供参考）：" + "；".join(f"{item['label']}：{item['detail']}" for item in flags))
        files = [row for row in evidence["per_tool"].get(tool, {}).get("files", []) if row.get("path")]
        if files:
            lines.append("- 证据：" + "，".join(f"{row['label']} `{row['path']}`" for row in files))
        lines.append("")
    shared = [row for row in evidence["shared"] if row.get("path")]
    if shared:
        lines += ["## 本期共用证据", ""] + [f"- {row['label']}：`{row['path']}`" for row in shared] + [""]
    lines += ["## 图片顺序", ""] + [f"{index}. {image.get('label', '')}" for index, image in enumerate(topic.get("images", []), 1)] + [""]
    lines += ["## 标题备选", ""] + [f"- {title}" for title in topic.get("titles", [])]
    if topic.get("title_note"):
        lines += ["", f"⚠️ {topic['title_note']}"]
    blockers = readiness.get("blockers") or []
    lines += ["", "## 复核前还缺什么", ""]
    lines += [f"- {item['message']}" for item in blockers] or ["- 内容已齐，可以在工作台点“我已逐条核对”"]
    lines.append("")
    return "\n".join(lines)


def write_handoff(project: Project, post_id: str) -> Path:
    target = project.post_dir(post_id) / "handoff.md"
    write_text(target, handoff_markdown(project, post_id))
    return target


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("用法：python scripts/handoff.py <post_id>", file=sys.stderr)
        return 2
    project = Project()
    path = write_handoff(project, args[0])
    print(f"已生成 {path.relative_to(project.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
