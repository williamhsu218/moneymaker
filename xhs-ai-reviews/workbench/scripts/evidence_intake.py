#!/usr/bin/env python3
"""Get raw evidence into a post without hand-editing JSON.

Phone screenshots go into posts/<post_id>/inbox/ (AirDrop is fine). This
module lists them, suggests which tool/evidence each belongs to, converts HEIC
on macOS, and files them as evidence/<tool>/<name>.<ext> while updating
evidence/manifest.json. Replaced files are moved to evidence/<tool>/_replaced/,
never deleted; imported originals are moved to inbox/_imported/.

    python scripts/evidence_intake.py post-01-weekly-report --list
    python scripts/evidence_intake.py post-01-weekly-report --auto
    python scripts/evidence_intake.py post-01-weekly-report --assign IMG_0012.PNG deepseek prompt_a_screenshot
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.project import (
    HEIC_EXTS, SHARED_SCOPE, Project, ProjectError, image_kind, load_json, valid_datetime, write_bytes, write_json,
    write_text,
)
from scripts.readiness import METADATA_FIELDS

TEXT_EXTS = ("txt", "md")
IMAGE_FILE_EXTS = ["png", "jpg", "jpeg", "webp", "heic", "heif"]
MAX_TEXT_BYTES = 2 * 1024 * 1024


class IntakeError(ProjectError):
    pass


def _manifest_path(project: Project, post_id: str) -> Path:
    return project.post_dir(post_id) / "evidence" / "manifest.json"


def load_manifest(project: Project, post_id: str) -> Dict[str, Any]:
    manifest = load_json(_manifest_path(project, post_id), {}) or {}
    manifest.setdefault("tools", {})
    manifest.setdefault("shared", {})
    manifest.setdefault("shared_sources", {})
    for tool in project.post_tools(post_id):
        entry = manifest["tools"].setdefault(tool, {})
        for field in METADATA_FIELDS:
            entry.setdefault(field, "")
        entry.setdefault("files", {})
        entry.setdefault("sources", {})
    return manifest


SOURCES = {"pasted": "你粘贴的原文", "claude_transcribed": "Claude 从截图转写", "uploaded": "工作台上传", "inbox": "从 inbox 归档"}


def _record(project: Project, post_id: str, scope: str, key: str, relative: str, source: str) -> None:
    if source not in SOURCES:
        raise IntakeError(f"来源只能是：{'、'.join(SOURCES)}")
    manifest = load_manifest(project, post_id)
    if scope == SHARED_SCOPE:
        manifest["shared"][key] = relative
        manifest.setdefault("shared_sources", {})[key] = source
    else:
        manifest["tools"][scope]["files"][key] = relative
        manifest["tools"][scope].setdefault("sources", {})[key] = source
    write_json(_manifest_path(project, post_id), manifest)


def _set_aside(folder: Path, stem: str, *, exts: Optional[List[str]] = None, exact: Optional[str] = None) -> None:
    """Move earlier versions of one evidence item into _replaced/ (history, not deletion).

    Text evidence matches its exact file name; images and files match the stem
    plus their own extensions, so saving a screenshot never touches prompt-a.txt.
    """
    if not folder.is_dir():
        return
    for existing in folder.iterdir():
        if not existing.is_file():
            continue
        if exact is not None:
            if existing.name != exact:
                continue
        elif existing.stem != stem or existing.suffix.lower().lstrip(".") not in (exts or []):
            continue
        archive = folder / "_replaced"
        archive.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = archive / f"{existing.stem}-{stamp}{existing.suffix}"
        counter = 1
        while target.exists():
            target = archive / f"{existing.stem}-{stamp}-{counter}{existing.suffix}"
            counter += 1
        existing.rename(target)


def convert_heic(source: Path, target: Path) -> None:
    sips = shutil.which("sips")
    if not sips:
        raise IntakeError("HEIC 照片需要在 Mac 上转换（sips 不可用）。也可以在 iPhone 设置 → 相机 → 格式 里选“兼容性最佳”，截图本来就是 PNG。")
    target.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([sips, "-s", "format", "png", str(source), "--out", str(target)], capture_output=True, timeout=60)
    if result.returncode != 0 or image_kind(target) != "png":
        raise IntakeError("HEIC 转 PNG 失败，请在“照片”里导出为 JPG/PNG 再放进 inbox")


def store_bytes(project: Project, post_id: str, scope: str, key: str, filename: str, data: bytes, source: str = "uploaded") -> str:
    """File uploaded bytes as one evidence item and return its project path."""
    scope = project.check_scope(post_id, scope)
    spec = project.evidence_spec(post_id, scope, key)
    folder = project.post_dir(post_id) / "evidence" / scope
    folder.mkdir(parents=True, exist_ok=True)
    stem = spec["filename"]
    kind = spec["kind"]
    if kind == "text":
        if len(data) > MAX_TEXT_BYTES:
            raise IntakeError("文本太大（超过 2MB）")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise IntakeError("文本需为 UTF-8 编码") from exc
        return save_text(project, post_id, scope, key, text, source="pasted" if source == "uploaded" else source)
    if kind == "image":
        tmp = folder / f".incoming-{stem}"
        write_bytes(tmp, data)
        detected = image_kind(tmp)
        if detected == "heic" or Path(filename).suffix.lower().lstrip(".") in HEIC_EXTS:
            target = folder / f"{stem}.png"
            try:
                _set_aside(folder, stem, exts=IMAGE_FILE_EXTS)
                convert_heic(tmp, target)
            finally:
                tmp.unlink(missing_ok=True)
        elif detected in ("png", "jpeg", "webp"):
            ext = {"png": "png", "jpeg": "jpg", "webp": "webp"}[detected]
            target = folder / f"{stem}.{ext}"
            _set_aside(folder, stem, exts=IMAGE_FILE_EXTS)
            tmp.rename(target)
        else:
            tmp.unlink(missing_ok=True)
            raise IntakeError("不是 PNG/JPG/WebP/HEIC 图片")
    else:
        ext = Path(filename).suffix.lower().lstrip(".")
        allowed = [item.lower() for item in spec.get("exts", [])]
        if allowed and ext not in allowed:
            raise IntakeError(f"{spec['label']} 需要 {'/'.join(allowed)} 格式")
        if not data:
            raise IntakeError("文件是空的")
        target = folder / f"{stem}.{ext}"
        _set_aside(folder, stem, exts=allowed or [ext])
        write_bytes(target, data)
    relative = project.rel(target)
    _record(project, post_id, scope, key, relative, source)
    return relative


def save_text(project: Project, post_id: str, scope: str, key: str, text: str, source: str = "pasted") -> str:
    """Save a pasted raw answer exactly as given (only line endings are normalized)."""
    scope = project.check_scope(post_id, scope)
    spec = project.evidence_spec(post_id, scope, key)
    if spec["kind"] != "text":
        raise IntakeError(f"{spec['label']} 不是文本证据")
    if not isinstance(text, str):
        raise IntakeError("文本内容无效")
    folder = project.post_dir(post_id) / "evidence" / scope
    target = folder / spec["filename"]
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if target.exists():
        try:
            unchanged = target.read_text(encoding="utf-8") == normalized
        except (OSError, UnicodeError):
            unchanged = False
        if not unchanged:
            _set_aside(folder, spec["filename"], exact=spec["filename"])
    write_text(target, normalized)
    relative = project.rel(target)
    _record(project, post_id, scope, key, relative, source)
    return relative


def set_metadata(project: Project, post_id: str, tool: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    tool = project.check_scope(post_id, tool)
    if tool == SHARED_SCOPE:
        raise IntakeError("共用证据没有工具信息")
    manifest = load_manifest(project, post_id)
    entry = manifest["tools"][tool]
    for field in METADATA_FIELDS:
        if field in fields:
            value = fields[field]
            if value is None:
                value = ""
            if not isinstance(value, str) or len(value) > 500:
                raise IntakeError(f"{field} 需为 500 字以内的文字")
            if field == "tested_at" and value and not valid_datetime(value):
                raise IntakeError("测试时间格式应为 2026-09-28T20:30 这样的日期时间")
            entry[field] = value.strip()
    write_json(_manifest_path(project, post_id), manifest)
    return entry


# ----------------------------------------------------------------------- inbox
def _inbox(project: Project, post_id: str) -> Path:
    return project.post_dir(post_id) / "inbox"


def _aliases(project: Project, tool: str) -> List[str]:
    info = project.tool_map().get(tool, {})
    names = {tool, tool.replace("_", ""), str(info.get("display_name", "")), str(info.get("app_name", ""))}
    names |= {name.replace("腾讯", "") for name in names}
    return sorted((name.lower() for name in names if name and len(name) >= 2), key=len, reverse=True)


def suggest(project: Project, post_id: str, filename: str) -> Optional[Dict[str, str]]:
    """Guess tool + evidence from names like deepseek-prompt-a.png or 豆包_q1.jpg."""
    name = Path(filename).stem.lower()
    topic = project.post_topic(post_id)
    specs = topic.get("evidence") or {}
    scope = None
    rest = name
    for tool in project.post_tools(post_id):
        for alias in _aliases(project, tool):
            if alias in name:
                scope = tool
                rest = name.replace(alias, " ")
                break
        if scope:
            break
    candidates = specs.get("per_tool", []) if scope else specs.get("shared", [])
    if scope is None and not candidates:
        return None
    ext = Path(filename).suffix.lower().lstrip(".")
    wants_text = ext in TEXT_EXTS
    fitting = [spec for spec in candidates if (spec["kind"] == "text") == wants_text]
    tokens = re.sub(r"[^a-z0-9一-鿿]+", " ", rest).split()
    joined = "-".join(tokens)
    best = None
    for spec in sorted(fitting, key=lambda item: len(item["filename"]), reverse=True):
        stem = spec["filename"].split(".")[0].lower()
        if stem and stem in joined:
            best = spec
            break
    if best is None and tokens:
        last = tokens[-1]
        matches = [spec for spec in fitting if spec["filename"].split(".")[0].lower().endswith("-" + last)]
        if len(matches) == 1:
            best = matches[0]
    if best is None and len(fitting) == 1:
        best = fitting[0]
    if best is None:
        return None
    return {"scope": scope or SHARED_SCOPE, "key": best["key"]}


def list_inbox(project: Project, post_id: str) -> List[Dict[str, Any]]:
    inbox = _inbox(project, post_id)
    if not inbox.is_dir():
        return []
    items = []
    for path in sorted(inbox.iterdir(), key=lambda item: item.stat().st_mtime):
        if not path.is_file() or path.name.startswith("."):
            continue
        detected = image_kind(path)
        ext = path.suffix.lower().lstrip(".")
        kind = "image" if detected else ("text" if ext in TEXT_EXTS else "file")
        items.append({
            "name": path.name,
            "size": path.stat().st_size,
            "mtime": path.stat().st_mtime,
            "kind": "heic" if detected == "heic" else kind,
            "suggestion": suggest(project, post_id, path.name),
        })
    return items


def _inbox_file(project: Project, post_id: str, name: str) -> Path:
    if not isinstance(name, str) or "/" in name or "\\" in name or name.startswith("."):
        raise IntakeError("文件名无效")
    path = _inbox(project, post_id) / name
    if not path.is_file():
        raise IntakeError(f"inbox 里没有 {name}")
    return path


def assign_inbox_file(project: Project, post_id: str, name: str, scope: str, key: str) -> str:
    source = _inbox_file(project, post_id, name)
    relative = store_bytes(project, post_id, scope, key, source.name, source.read_bytes(), source="inbox")
    done = _inbox(project, post_id) / "_imported"
    done.mkdir(exist_ok=True)
    target = done / source.name
    if target.exists():
        target = done / f"{source.stem}-{datetime.now().strftime('%H%M%S')}{source.suffix}"
    source.rename(target)
    return relative


def auto_assign(project: Project, post_id: str) -> List[Dict[str, str]]:
    assigned = []
    for item in list_inbox(project, post_id):
        suggestion = item.get("suggestion")
        if not suggestion:
            continue
        try:
            relative = assign_inbox_file(project, post_id, item["name"], suggestion["scope"], suggestion["key"])
            assigned.append({"name": item["name"], **suggestion, "path": relative})
        except ProjectError as exc:
            assigned.append({"name": item["name"], **suggestion, "error": str(exc)})
    return assigned


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把 inbox 里的截图和文件归档为证据")
    parser.add_argument("post_id")
    parser.add_argument("--list", action="store_true", help="列出 inbox 文件和建议归属")
    parser.add_argument("--auto", action="store_true", help="按文件名自动归档能识别的文件")
    parser.add_argument("--assign", nargs=3, metavar=("FILE", "TOOL_OR_shared", "KEY"))
    args = parser.parse_args(argv)
    project = Project()
    try:
        if args.assign:
            print(assign_inbox_file(project, args.post_id, *args.assign))
        elif args.auto:
            print(json.dumps(auto_assign(project, args.post_id), ensure_ascii=False, indent=2))
        else:
            print(json.dumps(list_inbox(project, args.post_id), ensure_ascii=False, indent=2))
    except ProjectError as exc:
        print(f"未完成：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
