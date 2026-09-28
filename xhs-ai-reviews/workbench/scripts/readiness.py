"""Publication gate for any post: fail closed until evidence, review and assets agree.

A post is publishable only when:
  1. every tool has complete, consistent human scoring (scorecard "verified");
  2. every required evidence file exists, is the right kind, and sits in that
     tool's own folder; tool metadata (model, version, ...) is filled in;
  3. copy.md and text cards pass the blocking publish checks;
  4. the one-click review recorded SHA-256 hashes of every claim-bearing file,
     and none of them changed since;
  5. the rendered images carry no draft mark and were rendered from exactly
     that review.

``review_post`` performs step 4 on the server so nobody hashes files by hand.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from scripts.project import (
        HEIC_EXTS, IMAGE_EXTS, SHARED_SCOPE, Project, ProjectError, image_kind, load_json, now_iso,
        sha256_file, valid_date, valid_datetime, write_json,
    )
    from scripts.publish_lint import lint_cards, lint_post
except ImportError:  # pragma: no cover
    from project import (  # type: ignore
        HEIC_EXTS, IMAGE_EXTS, SHARED_SCOPE, Project, ProjectError, image_kind, load_json, now_iso,
        sha256_file, valid_date, valid_datetime, write_json,
    )
    from publish_lint import lint_cards, lint_post  # type: ignore

METADATA_FIELDS = ("model", "version", "platform", "settings", "free_tier", "tested_at")
METADATA_LABELS = {"model": "模型", "version": "版本", "platform": "平台/入口", "settings": "设置", "free_tier": "免费额度", "tested_at": "测试时间"}
REVIEW_EXTRA_FILES = ("copy.md", "cards.json", "highlights.json", "post.json")
BOOLEAN_VALUES = {"pass", "fail"}


def evidence_file_ok(project: Project, post_dir: Path, scope: str, spec: Dict[str, Any], relative: Any) -> Tuple[bool, str, Optional[Path]]:
    """Validate one evidence file against its spec. Returns (ok, reason, path)."""
    if not isinstance(relative, str) or not relative.strip():
        return False, "未录入", None
    try:
        path = project.resolve_inside(relative, post_dir / "evidence" / scope)
    except ProjectError:
        return False, "路径不在本工具的证据文件夹里", None
    if path.parent != (post_dir / "evidence" / scope).resolve():
        return False, "路径不在本工具的证据文件夹里", None
    if not path.is_file():
        return False, "文件不存在", None
    kind = spec.get("kind")
    stem = spec.get("filename", "")
    if kind == "text":
        if path.name != stem:
            return False, f"文件名应为 {stem}", None
        try:
            if len(path.read_text(encoding="utf-8").strip()) < 10:
                return False, "原文太短（少于 10 字）", None
        except (OSError, UnicodeError):
            return False, "不是 UTF-8 文本", None
        return True, "", path
    ext = path.suffix.lower().lstrip(".")
    if path.stem != stem:
        return False, f"文件名应为 {stem}.扩展名", None
    if kind == "image":
        if ext in HEIC_EXTS or image_kind(path) == "heic":
            return False, "HEIC 需先转成 PNG/JPG", None
        if ext not in IMAGE_EXTS or image_kind(path) is None or path.stat().st_size <= 100:
            return False, "不是有效的 PNG/JPG/WebP 图片", None
        return True, "", path
    allowed = [item.lower() for item in spec.get("exts", [])]
    if allowed and ext not in allowed:
        return False, f"格式应为 {'/'.join(allowed)}", None
    if path.stat().st_size == 0:
        return False, "文件是空的", None
    return True, "", path


def _check_value_ok(check: Dict[str, Any], value: Any) -> bool:
    kind = check.get("type", "boolean")
    if kind == "boolean":
        return value in BOOLEAN_VALUES
    if kind == "enum":
        return value in (check.get("options") or [])
    if kind == "number":
        if type(value) not in (int, float):
            return False
        if "min" in check and value < check["min"]:
            return False
        if "max" in check and value > check["max"]:
            return False
        return True
    return isinstance(value, str) and bool(value.strip())


def scorecard_problems(scorecard: Dict[str, Any], tools: List[str]) -> List[str]:
    """Human scoring must be complete and internally consistent for every tool."""
    problems: List[str] = []
    checks = scorecard.get("checks") or {}
    overall = scorecard.get("overall") or {}
    results = scorecard.get("tool_results") or {}
    for tool in tools:
        result = results.get(tool)
        if not isinstance(result, dict):
            problems.append(f"{tool}：还没有评分")
            continue
        values = result.get("checks") or {}
        notes = result.get("notes") or {}
        for check_id, check in checks.items():
            required = check.get("required", True)
            value = values.get(check_id)
            if value in (None, "", "pending"):
                if required:
                    problems.append(f"{tool}：“{check.get('name', check_id)}”待评")
                continue
            if not _check_value_ok(check, value):
                problems.append(f"{tool}：“{check.get('name', check_id)}”的值无效")
                continue
            if check.get("type", "boolean") == "boolean":
                note = notes.get(check_id)
                if not isinstance(note, str) or not note.strip():
                    problems.append(f"{tool}：“{check.get('name', check_id)}”缺少对照原文的依据")
                elif (value == "pass" and "踩坑" in note) or (value == "fail" and note.strip().startswith("通过")):
                    problems.append(f"{tool}：“{check.get('name', check_id)}”的判定和依据说法矛盾")
        score = result.get("total_score")
        if overall.get("required", True):
            if type(score) not in (int, float) or not 1 <= score <= 5:
                problems.append(f"{tool}：{overall.get('label', '总评')}需要 1–5 分")
        elif score is not None and (type(score) not in (int, float) or not 1 <= score <= 5):
            problems.append(f"{tool}：总评分数需在 1–5 之间")
        for key, label in (("verdict", "人工结论"), ("summary", "一句话结论"), ("gut_reaction", "你自己的一句真实感受")):
            if not isinstance(result.get(key), str) or not result[key].strip():
                problems.append(f"{tool}：缺少{label}")
    return problems


def evidence_status(project: Project, post_id: str, manifest: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Per-tool and shared evidence completeness, used by the gate and the UI."""
    post_dir = project.post_dir(post_id)
    topic = project.post_topic(post_id)
    tools = project.post_tools(post_id)
    manifest = manifest if manifest is not None else (load_json(post_dir / "evidence" / "manifest.json", {}) or {})
    specs = topic.get("evidence") or {}
    per_tool: Dict[str, Any] = {}
    used: List[Path] = []
    problems: List[str] = []
    for tool in tools:
        item = (manifest.get("tools") or {}).get(tool) or {}
        files = item.get("files") or {}
        rows = []
        for spec in specs.get("per_tool", []):
            ok, reason, path = evidence_file_ok(project, post_dir, tool, spec, files.get(spec["key"]))
            required = spec.get("required", True)
            rows.append({"key": spec["key"], "label": spec["label"], "kind": spec["kind"], "required": required, "ok": ok, "reason": reason, "path": files.get(spec["key"])})
            if ok and path is not None:
                used.append(path)
            elif required or files.get(spec["key"]):
                problems.append(f"{project.tool_name(tool)}：{spec['label']}{'（' + reason + '）' if reason else ''}")
        missing_meta = [METADATA_LABELS[field] for field in METADATA_FIELDS if not (isinstance(item.get(field), str) and item[field].strip())]
        if item.get("tested_at") and not valid_datetime(item.get("tested_at")):
            missing_meta.append("测试时间格式")
        if missing_meta:
            problems.append(f"{project.tool_name(tool)}：缺少{'、'.join(missing_meta)}")
        per_tool[tool] = {"files": rows, "missing_metadata": missing_meta, "complete": all(row["ok"] or not row["required"] for row in rows) and not missing_meta}
    shared_rows = []
    shared_files = manifest.get("shared") or {}
    for spec in specs.get("shared", []):
        ok, reason, path = evidence_file_ok(project, post_dir, SHARED_SCOPE, spec, shared_files.get(spec["key"]))
        required = spec.get("required", True)
        shared_rows.append({"key": spec["key"], "label": spec["label"], "kind": spec["kind"], "required": required, "ok": ok, "reason": reason, "path": shared_files.get(spec["key"])})
        if ok and path is not None:
            used.append(path)
        elif required or shared_files.get(spec["key"]):
            problems.append(f"本期共用：{spec['label']}{'（' + reason + '）' if reason else ''}")
    required_count = sum(1 for spec in specs.get("per_tool", []) if spec.get("required", True)) * len(tools) + sum(1 for spec in specs.get("shared", []) if spec.get("required", True))
    return {"per_tool": per_tool, "shared": shared_rows, "problems": problems, "used_paths": used, "count": len(used), "required_count": required_count}


def review_file_set(project: Project, post_id: str, used_paths: List[Path]) -> List[Path]:
    post_dir = project.post_dir(post_id)
    paths = [post_dir / "scorecard.json"] + [post_dir / name for name in REVIEW_EXTRA_FILES]
    return [path for path in paths if path.is_file()] + list(used_paths)


def compute_hashes(project: Project, paths: List[Path]) -> Dict[str, str]:
    return {project.rel(path): sha256_file(path) or "" for path in paths}


META_KEY = "evidence/manifest.json#metadata"


def metadata_digest(manifest: Dict[str, Any]) -> str:
    """Tool metadata (model, version, file map) is claim-bearing too."""
    payload = {"tools": manifest.get("tools") or {}, "shared": manifest.get("shared") or {}}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def fingerprint(hashes: Dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(sorted(hashes.items()), ensure_ascii=False).encode("utf-8")).hexdigest()


def verified_post_count(project: Project, exclude: str = "") -> int:
    count = 0
    for other in project.list_posts():
        if other == exclude:
            continue
        scorecard = load_json(project.post_dir(other) / "scorecard.json", {}) or {}
        manifest = load_json(project.post_dir(other) / "evidence" / "manifest.json", {}) or {}
        if scorecard.get("status") != "verified" or not valid_date(scorecard.get("evaluation_date")):
            continue
        if not (manifest.get("status") == "reviewed" and manifest.get("claims_reviewed") is True
                and valid_datetime(manifest.get("reviewed_at"))
                and manifest.get("test_date") == scorecard.get("evaluation_date")):
            continue
        evidence = evidence_status(project, other, manifest)
        if evidence["problems"]:
            continue
        reviewed_hashes = manifest.get("reviewed_hashes") or {}
        current = compute_hashes(project, review_file_set(project, other, evidence["used_paths"]))
        current[META_KEY] = metadata_digest(manifest)
        if reviewed_hashes and current == reviewed_hashes:
            count += 1
    return count


def assets_status(project: Project, post_id: str, expected_fingerprint: Optional[str]) -> Dict[str, Any]:
    post_dir = project.post_dir(post_id)
    render = load_json(post_dir / "images" / "render.json", {}) or {}
    files = render.get("files") or []
    present = []
    ok = bool(files) and render.get("png_ok") is True
    for item in files:
        png = post_dir / "images" / str(item.get("png", ""))
        exists = png.is_file() and sha256_file(png) == item.get("sha256")
        present.append({"index": item.get("index"), "label": item.get("label"), "png": item.get("png"), "ok": exists})
        ok = ok and exists
    is_draft = render.get("draft", True) is not False
    fresh = ok and not is_draft and expected_fingerprint is not None and render.get("review_fingerprint") == expected_fingerprint
    return {"rendered": bool(files), "draft": is_draft, "fresh_final": fresh, "files": present, "generated_at": render.get("generated_at"), "png_ok": render.get("png_ok")}


def assess_post_readiness(project: Project, post_id: str, *, for_review: bool = False) -> Dict[str, Any]:
    """Return the gate state. ``for_review`` skips the review and asset steps."""
    post_dir = project.post_dir(post_id)
    topic = project.post_topic(post_id)
    tools = project.post_tools(post_id)
    blockers: List[Dict[str, Any]] = []
    checks: Dict[str, bool] = {}

    def fail(code: str, message: str, details: Optional[List[str]] = None) -> None:
        blockers.append({"code": code, "message": message, "details": (details or [])[:20]})

    scorecard = load_json(post_dir / "scorecard.json")
    if not isinstance(scorecard, dict):
        scorecard = {}
        fail("scorecard_missing", "评分卡缺失或格式无效")
    manifest = load_json(post_dir / "evidence" / "manifest.json")
    if not isinstance(manifest, dict):
        manifest = {}
        fail("manifest_missing", "证据清单缺失或格式无效")

    tools_ok = (
        len(tools) >= int(topic.get("min_tools", 1))
        and len(set(tools)) == len(tools)
        and all(tool in project.tool_map() for tool in tools)
        and scorecard.get("tools") == tools
    )
    checks["tools"] = tools_ok
    if not tools_ok:
        fail("tools_mismatch", f"参评工具需至少 {topic.get('min_tools', 1)} 款，且评分卡与篇目设置一致")

    problems = scorecard_problems(scorecard, tools) if scorecard else ["评分卡缺失"]
    checks["scoring_complete"] = not problems
    if problems:
        fail("scoring_incomplete", f"人工评分还有 {len(problems)} 处没填完或不一致", problems)

    evidence = evidence_status(project, post_id, manifest)
    checks["evidence_complete"] = not evidence["problems"]
    if evidence["problems"]:
        fail("evidence_incomplete", f"证据还缺 {len(evidence['problems'])} 项", evidence["problems"])

    lint = lint_post(project, post_id)
    card_problems = lint_cards(load_json(post_dir / "cards.json", {}) or {})
    checks["copy_ok"] = lint["ok"]
    if not lint["ok"]:
        fail("copy_blocked", f"文案还有 {len(lint['errors'])} 个必须处理的问题", [item["message"] for item in lint["errors"]])
    checks["cards_ok"] = not card_problems
    if card_problems:
        fail("cards_placeholder", "图片上的文字卡还有【】待填", [item["message"] for item in card_problems])

    required_posts = int(topic.get("requires_verified_posts") or 0)
    if required_posts:
        done = verified_post_count(project, exclude=post_id)
        checks["enough_posts"] = done >= required_posts
        if done < required_posts:
            fail("not_enough_posts", f"这一期要在至少 {required_posts} 期完成复核后再做（目前 {done} 期）")

    content_ready = not blockers
    result: Dict[str, Any] = {
        "post_id": post_id,
        "content_ready_for_review": content_ready,
        "checks": checks,
        "evidence_count": evidence["count"],
        "required_evidence_count": evidence["required_count"],
        "lint": {key: lint[key] for key in ("errors", "warnings", "reminders", "stats")},
    }
    if for_review:
        result["blockers"] = blockers
        return result

    status_ok = scorecard.get("status") == "verified" and valid_date(scorecard.get("evaluation_date"))
    checks["scorecard_verified"] = status_ok
    if not status_ok:
        fail("scorecard_draft", "评分卡还是草稿：内容齐了之后点“我已逐条核对”完成复核")

    reviewed_hashes = manifest.get("reviewed_hashes") or {}
    review_meta_ok = (
        manifest.get("status") == "reviewed"
        and manifest.get("claims_reviewed") is True
        and isinstance(manifest.get("reviewed_by"), str) and bool(manifest["reviewed_by"].strip())
        and valid_datetime(manifest.get("reviewed_at"))
        and manifest.get("test_date") == scorecard.get("evaluation_date")
    )
    current = compute_hashes(project, review_file_set(project, post_id, evidence["used_paths"]))
    current[META_KEY] = metadata_digest(manifest)
    changed = sorted(path for path in set(current) | set(reviewed_hashes) if current.get(path) != reviewed_hashes.get(path))
    hashes_ok = review_meta_ok and bool(reviewed_hashes) and not changed
    checks["review_recorded"] = review_meta_ok
    checks["review_current"] = hashes_ok
    if status_ok and not review_meta_ok:
        fail("review_pending", "还没有完成一键复核")
    elif review_meta_ok and changed:
        fail("review_stale", "复核后又有文件改动，需要重新点一次复核", changed)

    content_verified = not blockers
    expected = fingerprint(reviewed_hashes) if hashes_ok else None
    assets = assets_status(project, post_id, expected)
    checks["assets_fresh"] = assets["fresh_final"]
    if content_verified and not assets["fresh_final"]:
        fail("assets_stale", "复核通过后还要重新生成一次图片（去掉草稿标识）")
    publishable = content_verified and assets["fresh_final"]
    result.update({
        "status": "ready" if publishable else "needs_work",
        "content_verified": content_verified,
        "publishable": publishable,
        "blockers": blockers,
        "changed_since_review": changed if review_meta_ok else [],
        "assets": assets,
        "review_fingerprint": expected,
    })
    return result


def review_post(project: Project, post_id: str, reviewed_by: str, test_date: Optional[str] = None) -> Dict[str, Any]:
    """One-click review: verify content, then record hashes of every claim file."""
    if not isinstance(reviewed_by, str) or not reviewed_by.strip():
        raise ProjectError("请填写复核人")
    pre = assess_post_readiness(project, post_id, for_review=True)
    if not pre["content_ready_for_review"]:
        return {"status": "blocked", "readiness": pre}
    post_dir = project.post_dir(post_id)
    manifest = load_json(post_dir / "evidence" / "manifest.json", {}) or {}
    scorecard = load_json(post_dir / "scorecard.json", {}) or {}
    if test_date is None:
        stamps = [
            ((manifest.get("tools") or {}).get(tool) or {}).get("tested_at", "")
            for tool in project.post_tools(post_id)
        ]
        dates = sorted(datetime.fromisoformat(stamp.replace("Z", "+00:00")).date().isoformat() for stamp in stamps if valid_datetime(stamp))
        test_date = dates[-1] if dates else datetime.now().date().isoformat()
    if not valid_date(test_date):
        raise ProjectError("测试日期格式应为 YYYY-MM-DD")
    scorecard["status"] = "verified"
    scorecard["evaluator"] = reviewed_by.strip()
    scorecard["evaluation_date"] = test_date
    write_json(post_dir / "scorecard.json", scorecard)
    evidence = evidence_status(project, post_id, manifest)
    hashes = compute_hashes(project, review_file_set(project, post_id, evidence["used_paths"]))
    hashes[META_KEY] = metadata_digest(manifest)
    manifest.update({
        "status": "reviewed",
        "test_date": test_date,
        "reviewed_by": reviewed_by.strip(),
        "reviewed_at": now_iso(),
        "claims_reviewed": True,
        "reviewed_hashes": hashes,
    })
    write_json(post_dir / "evidence" / "manifest.json", manifest)
    return {"status": "reviewed", "locked_files": sorted(hashes), "readiness": assess_post_readiness(project, post_id)}
