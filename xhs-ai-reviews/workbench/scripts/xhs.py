#!/usr/bin/env python3
"""One command-line entry for Claude (Opus 5.5 in Cowork) and for you.

Claude uses these commands to work on the project files, so nothing is edited
by hand and every write goes through the same checks as the workbench.
Payloads are read from stdin; results are printed as JSON.

    python3 scripts/xhs.py status                         # all posts, what's next and who does it
    python3 scripts/xhs.py status post-01-weekly-report   # one post: blockers + next step
    python3 scripts/xhs.py new 02
    python3 scripts/xhs.py inbox post-01-weekly-report
    python3 scripts/xhs.py file  post-01-weekly-report IMG_0012.PNG deepseek prompt_a_screenshot
    python3 scripts/xhs.py text  post-01-weekly-report deepseek prompt_a_text --source claude_transcribed < answer.txt
    python3 scripts/xhs.py meta  post-01-weekly-report deepseek model="DeepSeek-V3" tested_at=2026-09-28T20:30:00+08:00
    python3 scripts/xhs.py prechecks post-01-weekly-report
    python3 scripts/xhs.py suggest post-01-weekly-report < suggestions.json
    python3 scripts/xhs.py boxes post-01-weekly-report deepseek prompt_a_screenshot < boxes.json
    python3 scripts/xhs.py copy  post-01-weekly-report < copy.md
    python3 scripts/xhs.py cards post-01-weekly-report < cards.json
    python3 scripts/xhs.py results post-01-weekly-report          # what you accepted + your reactions
    python3 scripts/xhs.py lint  post-01-weekly-report
    python3 scripts/xhs.py render post-01-weekly-report [--html-only]
    python3 scripts/xhs.py metric post-01-weekly-report 24h views=1200 saves=96 new_followers=18
    python3 scripts/xhs.py request "测AI写小红书文案"
    python3 scripts/xhs.py lead title="千问上线视频理解" url=https://... tool=qianwen
    python3 scripts/xhs.py review-week 1
    python3 scripts/xhs.py ops-inbox                     # data-page screenshots waiting in ops/inbox/
    python3 scripts/xhs.py ops-done IMG_2001.PNG         # move a processed data screenshot to _done/

Never run review, mark-published or anything that publishes: those stay with you.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ops
from scripts.evidence_intake import SOURCES, assign_inbox_file, list_inbox, load_manifest, save_text, set_metadata
from scripts.new_post import create_post
from scripts.prechecks import run_prechecks
from scripts.project import SHARED_SCOPE, Project, ProjectError, image_size, load_json, write_json, write_text
from scripts.publish_lint import lint_cards, lint_post
from scripts.readiness import assess_post_readiness, evidence_status
from scripts.render_carousel import render_post
from scripts.suggestions import load_suggestions, save_suggestions
from scripts.weekly_review import write_review
from scripts.workflow import next_step

def out(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def stdin_json() -> Any:
    raw = sys.stdin.read()
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ProjectError(f"标准输入不是有效的 JSON：{exc}") from exc


def pairs(items: List[str]) -> Dict[str, str]:
    result = {}
    for item in items:
        if "=" not in item:
            raise ProjectError(f"参数应为 key=value：{item}")
        key, value = item.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def cmd_status(project: Project, args) -> None:
    if args.post_id:
        readiness = assess_post_readiness(project, args.post_id)
        out({
            "post_id": args.post_id,
            "publishable": readiness["publishable"],
            "next": next_step(project, args.post_id),
            "evidence": f"{readiness['evidence_count']}/{readiness['required_evidence_count']}",
            "blockers": [{"code": item["code"], "message": item["message"], "details": item.get("details", [])[:8]} for item in readiness["blockers"]],
            "changed_since_review": readiness.get("changed_since_review", []),
        })
        return
    calendar = ops.load_calendar(project)
    slots = [slot for week in calendar["weeks"] for slot in week["slots"]]
    out({
        "posts": [{"post_id": post_id, "next": next_step(project, post_id)} for post_id in project.list_posts()],
        "upcoming": [{"date": slot["date"], "topic_id": slot.get("topic_id"), "post_id": slot.get("post_id"), "status": slot.get("status")} for slot in slots if slot.get("status") not in ("已发布", "跳过")][:6],
    })


def cmd_new(project: Project, args) -> None:
    post_id = create_post(project, args.topic_id.zfill(2), tools=args.tools, slug=args.slug)
    ops.attach_post(project, args.topic_id.zfill(2), post_id)
    out({"post_id": post_id, "inbox": f"posts/{post_id}/inbox/"})


def cmd_inbox(project: Project, args) -> None:
    items = list_inbox(project, args.post_id)
    folder = project.post_dir(args.post_id) / "inbox"
    for item in items:
        size = image_size(folder / item["name"])
        item["pixels"] = f"{size[0]}x{size[1]}" if size else None
        item["path"] = f"posts/{args.post_id}/inbox/{item['name']}"
    topic = project.post_topic(args.post_id)
    out({
        "files": items,
        "targets": {
            "per_tool": [{"key": spec["key"], "kind": spec["kind"], "label": spec["label"]} for spec in topic["evidence"]["per_tool"]],
            "shared": [{"key": spec["key"], "kind": spec["kind"], "label": spec["label"]} for spec in topic["evidence"].get("shared", [])],
            "tools": project.post_tools(args.post_id),
        },
    })


def cmd_file(project: Project, args) -> None:
    out({"path": assign_inbox_file(project, args.post_id, args.name, args.scope, args.key)})


def cmd_text(project: Project, args) -> None:
    text = sys.stdin.read()
    out({"path": save_text(project, args.post_id, args.scope, args.key, text, source=args.source), "chars": len(text.strip())})


def cmd_meta(project: Project, args) -> None:
    out(set_metadata(project, args.post_id, args.tool, pairs(args.fields)))


def cmd_prechecks(project: Project, args) -> None:
    report = run_prechecks(project, args.post_id)
    compact = {tool: [{k: item.get(k) for k in ("check", "label", "status", "detail")} | ({"hits": [hit.get("context") or hit.get("match") for hit in item.get("hits", [])[:4]]} if item.get("hits") else {}) for item in items] for tool, items in report["results"].items()}
    out(compact)


def cmd_suggest(project: Project, args) -> None:
    data = save_suggestions(project, args.post_id, stdin_json(), merge=not args.replace)
    out({"saved": True, "tools": sorted(data["tools"])})


def cmd_boxes(project: Project, args) -> None:
    payload = stdin_json()
    project.check_scope(args.post_id, args.tool)
    project.evidence_spec(args.post_id, args.tool, args.key)
    from scripts.radar_dashboard import save_highlights
    saved = save_highlights(project, args.post_id, {"tool": args.tool, "key": args.key, **payload})[args.tool][args.key]
    out({"saved": True, "boxes": len(saved["boxes"]), "masks": len(saved["masks"])})


def cmd_copy(project: Project, args) -> None:
    text = sys.stdin.read()
    if len(text.strip()) < 20:
        raise ProjectError("文案内容太短")
    write_text(project.post_dir(args.post_id) / "copy.md", text.replace("\r\n", "\n"))
    report = lint_post(project, args.post_id)
    out({"saved": True, "errors": [item["message"] for item in report["errors"]], "warnings": [item["message"] for item in report["warnings"]], "stats": report["stats"]})


def cmd_cards(project: Project, args) -> None:
    from scripts.radar_dashboard import save_cards
    current = load_json(project.post_dir(args.post_id) / "cards.json", {}) or {}
    current.update(stdin_json())
    cards = save_cards(project, args.post_id, {"cards": current})
    out({"saved": True, "problems": [item["message"] for item in lint_cards(cards)]})


def cmd_results(project: Project, args) -> None:
    scorecard = load_json(project.post_dir(args.post_id) / "scorecard.json", {}) or {}
    manifest = load_manifest(project, args.post_id)
    out({
        "status": scorecard.get("status"),
        "checks": {key: check.get("name") for key, check in (scorecard.get("checks") or {}).items()},
        "tools": {
            tool: {
                "name": project.tool_name(tool),
                "model": (manifest["tools"].get(tool) or {}).get("model"),
                **{key: result.get(key) for key in ("checks", "notes", "total_score", "verdict", "summary", "gut_reaction", "keep_using")},
            }
            for tool, result in (scorecard.get("tool_results") or {}).items()
        },
    })


def cmd_lint(project: Project, args) -> None:
    report = lint_post(project, args.post_id)
    report.pop("parsed", None)
    out(report)


def cmd_render(project: Project, args) -> None:
    result = render_post(project, args.post_id, export=not args.html_only)
    out({"status": result["status"], "draft": result["draft"], "engine": result["engine"], "files": [f"posts/{args.post_id}/images/{entry['png']}" for entry in result["files"]]})


def cmd_metric(project: Project, args) -> None:
    row = {"post_id": args.post_id, "checkpoint": args.checkpoint, **pairs(args.fields)}
    out(ops.upsert_metric(project, row))


def cmd_request(project: Project, args) -> None:
    out(ops.add_request(project, {"request": args.text, "post_id": args.post_id or ""}))


def cmd_lead(project: Project, args) -> None:
    out(ops.add_lead(project, pairs(args.fields)))


def cmd_ops_inbox(project: Project, args) -> None:
    folder = project.ops_dir / "inbox"
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for path in sorted(folder.iterdir(), key=lambda item: item.stat().st_mtime):
        if path.is_file() and not path.name.startswith("."):
            files.append({"name": path.name, "path": project.rel(path), "mtime": path.stat().st_mtime, "size": path.stat().st_size})
    published = []
    for week in ops.load_calendar(project)["weeks"]:
        for slot in week["slots"]:
            if slot.get("post_id") and slot.get("published_at"):
                published.append({"post_id": slot["post_id"], "published_at": slot["published_at"], "title": project.post_topic(slot["post_id"]).get("title")})
    out({"files": files, "published_posts": published, "note": "识别完一张就用 done 命令移到 ops/inbox/_done/"})


def cmd_ops_done(project: Project, args) -> None:
    folder = project.ops_dir / "inbox"
    source = folder / args.name
    if "/" in args.name or not source.is_file():
        raise ProjectError("ops/inbox 里没有这个文件")
    done = folder / "_done"
    done.mkdir(exist_ok=True)
    source.rename(done / source.name)
    out({"moved": f"ops/inbox/_done/{source.name}"})


def cmd_review_week(project: Project, args) -> None:
    path = write_review(project, args.week)
    out({"path": project.rel(path)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="科技试吃员工作流命令（给 Claude 和你用）")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("status"); p.add_argument("post_id", nargs="?"); p.set_defaults(func=cmd_status)
    p = sub.add_parser("new"); p.add_argument("topic_id"); p.add_argument("--slug"); p.add_argument("--tools", nargs="+"); p.set_defaults(func=cmd_new)
    p = sub.add_parser("inbox"); p.add_argument("post_id"); p.set_defaults(func=cmd_inbox)
    p = sub.add_parser("file"); p.add_argument("post_id"); p.add_argument("name"); p.add_argument("scope", help=f"工具 id 或 {SHARED_SCOPE}"); p.add_argument("key"); p.set_defaults(func=cmd_file)
    p = sub.add_parser("text"); p.add_argument("post_id"); p.add_argument("scope"); p.add_argument("key"); p.add_argument("--source", default="pasted", choices=sorted(SOURCES)); p.set_defaults(func=cmd_text)
    p = sub.add_parser("meta"); p.add_argument("post_id"); p.add_argument("tool"); p.add_argument("fields", nargs="+"); p.set_defaults(func=cmd_meta)
    p = sub.add_parser("prechecks"); p.add_argument("post_id"); p.set_defaults(func=cmd_prechecks)
    p = sub.add_parser("suggest"); p.add_argument("post_id"); p.add_argument("--replace", action="store_true"); p.set_defaults(func=cmd_suggest)
    p = sub.add_parser("boxes"); p.add_argument("post_id"); p.add_argument("tool"); p.add_argument("key"); p.set_defaults(func=cmd_boxes)
    p = sub.add_parser("copy"); p.add_argument("post_id"); p.set_defaults(func=cmd_copy)
    p = sub.add_parser("cards"); p.add_argument("post_id"); p.set_defaults(func=cmd_cards)
    p = sub.add_parser("results"); p.add_argument("post_id"); p.set_defaults(func=cmd_results)
    p = sub.add_parser("lint"); p.add_argument("post_id"); p.set_defaults(func=cmd_lint)
    p = sub.add_parser("render"); p.add_argument("post_id"); p.add_argument("--html-only", action="store_true"); p.set_defaults(func=cmd_render)
    p = sub.add_parser("metric"); p.add_argument("post_id"); p.add_argument("checkpoint", choices=ops.CHECKPOINTS); p.add_argument("fields", nargs="*"); p.set_defaults(func=cmd_metric)
    p = sub.add_parser("request"); p.add_argument("text"); p.add_argument("--post-id"); p.set_defaults(func=cmd_request)
    p = sub.add_parser("lead"); p.add_argument("fields", nargs="+"); p.set_defaults(func=cmd_lead)
    p = sub.add_parser("review-week"); p.add_argument("week", type=int); p.set_defaults(func=cmd_review_week)
    p = sub.add_parser("ops-inbox"); p.set_defaults(func=cmd_ops_inbox)
    p = sub.add_parser("ops-done"); p.add_argument("name"); p.set_defaults(func=cmd_ops_done)
    return parser


def main(argv=None, project: Project = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(project or Project(), args)
    except ProjectError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
