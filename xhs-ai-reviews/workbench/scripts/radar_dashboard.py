#!/usr/bin/env python3
"""Local workbench server (standard library only).

Serves web/ and a JSON API over the project files. Binds to 127.0.0.1; writes
are accepted only from same-port loopback pages. Nothing here publishes,
comments or otherwise operates a 小红书 account.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import logging
import math
import mimetypes
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ops
from scripts.evidence_intake import assign_inbox_file, auto_assign, list_inbox, load_manifest, save_text, set_metadata, store_bytes
from scripts.handoff import write_handoff
from scripts.new_post import blank_result, blank_tool_entry, create_post
from scripts.prechecks import run_prechecks
from scripts.project import (
    IMAGE_EXTS, SHARED_SCOPE, Project, ProjectError, image_kind, load_json, write_bytes, write_json, write_text,
)
from scripts.publish_lint import lint_cards, lint_copy
from scripts.readiness import METADATA_FIELDS, assess_post_readiness, evidence_status, review_post
from scripts.render_carousel import render_post
from scripts.suggestions import load_suggestions
from scripts.workflow import PHRASES, next_step
from scripts.weekly_review import write_review
from scripts.xhs_radar import (
    DEFAULT_MOCK_DATA, RadarScanner, RadarUnavailableError, appstore_check, appstore_confirm, appstore_resolve,
    load_state, official_check,
)

logger = logging.getLogger("radar_dashboard")
MAX_BODY = 80 * 1024 * 1024
POST_01 = "post-01-weekly-report"
WRITE_LOCK = threading.Lock()


def assess_post_01_readiness(project_root: Union[str, Path]) -> Dict[str, Any]:
    """Backward-compatible wrapper for the first post."""
    return assess_post_readiness(Project(project_root), POST_01)


# ------------------------------------------------------------------ test client
class TestResponse:
    def __init__(self, status_code: int, headers: Dict[str, str], content: bytes):
        self.status_code = status_code
        self.headers = headers
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class TestClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, json_data: Any = None, data: Optional[Union[bytes, str]] = None, headers: Optional[Dict[str, str]] = None) -> TestResponse:
        req_headers = dict(headers or {})
        body = None
        if json_data is not None:
            body = json.dumps(json_data, ensure_ascii=False).encode("utf-8")
            req_headers["Content-Type"] = "application/json; charset=utf-8"
        elif data is not None:
            body = data.encode("utf-8") if isinstance(data, str) else data
        req = urllib.request.Request(url=f"{self.base_url}/{path.lstrip('/')}", data=body, headers=req_headers, method=method.upper())
        try:
            with urllib.request.urlopen(req) as resp:
                return TestResponse(resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read())
        except urllib.error.HTTPError as err:
            return TestResponse(err.code, {k.lower(): v for k, v in err.headers.items()}, err.read())

    def get(self, path: str, headers: Optional[Dict[str, str]] = None) -> TestResponse:
        return self.request("GET", path, headers=headers)

    def post(self, path: str, json: Any = None, data: Optional[Union[bytes, str]] = None, headers: Optional[Dict[str, str]] = None) -> TestResponse:
        return self.request("POST", path, json_data=json, data=data, headers=headers)

    def options(self, path: str, headers: Optional[Dict[str, str]] = None) -> TestResponse:
        return self.request("OPTIONS", path, headers=headers)


# ----------------------------------------------------------------- post helpers
def image_urls(project: Project, post_id: str) -> Dict[str, Any]:
    render = load_json(project.post_dir(post_id) / "images" / "render.json", {}) or {}
    files = []
    for item in render.get("files", []):
        files.append({**item, "url": f"/assets/posts/{post_id}/images/{item.get('png')}", "html_url": f"/assets/posts/{post_id}/images/{item.get('html')}"})
    return {"draft": render.get("draft", True), "generated_at": render.get("generated_at"), "png_ok": render.get("png_ok"), "engine": render.get("engine"), "files": files}


def post_summary(project: Project, post_id: str) -> Dict[str, Any]:
    post = project.load_post(post_id)
    topic = project.post_topic(post_id)
    readiness = assess_post_readiness(project, post_id)
    return {
        "post_id": post_id,
        "topic_id": topic["id"],
        "name": topic.get("name"),
        "title": topic.get("title"),
        "format": topic.get("format"),
        "tools": [project.tool_name(tool) for tool in post.get("tools", [])],
        "publishable": readiness["publishable"],
        "content_verified": readiness["content_verified"],
        "content_ready_for_review": readiness["content_ready_for_review"],
        "evidence_count": readiness["evidence_count"],
        "required_evidence_count": readiness["required_evidence_count"],
        "blockers": [item["message"] for item in readiness["blockers"]][:4],
        "next": next_step(project, post_id),
    }


def post_detail(project: Project, post_id: str) -> Dict[str, Any]:
    post_dir = project.post_dir(post_id)
    post = project.load_post(post_id)
    topic = project.post_topic(post_id)
    manifest = load_manifest(project, post_id)
    evidence = evidence_status(project, post_id, manifest)
    evidence.pop("used_paths", None)
    rows = [row for tool in evidence["per_tool"].values() for row in tool["files"]] + evidence["shared"]
    for row in rows:
        path = project.root / row["path"] if row.get("path") else None
        row["mtime"] = int(path.stat().st_mtime) if path and path.is_file() else None
        if row["kind"] == "text" and path and path.is_file():
            try:
                row["text"] = path.read_text(encoding="utf-8")[:20000]
            except (OSError, UnicodeError):
                row["text"] = ""
    readiness = assess_post_readiness(project, post_id)
    copy_text = (post_dir / "copy.md").read_text(encoding="utf-8") if (post_dir / "copy.md").exists() else ""
    cards = load_json(post_dir / "cards.json", {}) or {}
    slot = None
    for week in ops.load_calendar(project)["weeks"]:
        for candidate in week["slots"]:
            if candidate.get("post_id") == post_id:
                slot = {**candidate, "week": week["week"]}
    lint = lint_copy(copy_text, project.brand())
    parsed = lint.pop("parsed")
    photos = sorted(path.name for path in (post_dir / "photos").glob("*") if path.suffix.lower().lstrip(".") in IMAGE_EXTS) if (post_dir / "photos").is_dir() else []
    return {
        "post": post,
        "topic": topic,
        "tools": [project.tool_map().get(tool, {"id": tool, "display_name": tool}) for tool in post.get("tools", [])],
        "scorecard": load_json(post_dir / "scorecard.json", {}) or {},
        "copy": copy_text,
        "copy_parsed": parsed,
        "cards": cards,
        "card_problems": lint_cards(cards),
        "highlights": load_json(post_dir / "highlights.json", {}) or {},
        "manifest": {key: manifest.get(key) for key in ("status", "test_date", "reviewed_by", "reviewed_at", "claims_reviewed", "tools", "shared", "shared_sources")},
        "evidence": evidence,
        "prechecks": run_prechecks(project, post_id),
        "lint": lint,
        "readiness": readiness,
        "images": image_urls(project, post_id),
        "photos": photos,
        "inbox": list_inbox(project, post_id),
        "metrics": [row for row in ops.load_metrics(project) if row["post_id"] == post_id],
        "slot": slot,
        "suggestions": load_suggestions(project, post_id),
        "next": next_step(project, post_id),
        "phrases": {key: value.format(id=topic["id"]) for key, value in PHRASES.items()},
    }


def update_settings(project: Project, post_id: str, body: Dict[str, Any]) -> None:
    post_dir = project.post_dir(post_id)
    post = project.load_post(post_id)
    topic = project.post_topic(post_id)
    if "tools" in body:
        tools = body["tools"]
        known = project.tool_map()
        if not isinstance(tools, list) or not all(isinstance(tool, str) and tool in known for tool in tools) or len(set(tools)) != len(tools):
            raise ProjectError("参评工具无效或重复")
        if len(tools) < int(topic.get("min_tools", 1)):
            raise ProjectError(f"这一期至少要 {topic.get('min_tools', 1)} 款工具")
        post["tools"] = tools
        scorecard = load_json(post_dir / "scorecard.json", {}) or {}
        results = scorecard.get("tool_results") or {}
        scorecard["tools"] = tools
        scorecard["tool_results"] = {tool: results.get(tool) or blank_result() for tool in tools}
        scorecard["status"] = "draft"
        write_json(post_dir / "scorecard.json", scorecard)
        manifest = load_json(post_dir / "evidence" / "manifest.json", {}) or {}
        old_tools = manifest.get("tools") or {}
        manifest["tools"] = {tool: old_tools.get(tool) or blank_tool_entry(topic) for tool in tools}
        write_json(post_dir / "evidence" / "manifest.json", manifest)
    if "cover" in body:
        cover = body["cover"]
        palettes = project.brand().get("palettes") or {}
        if not isinstance(cover, dict) or cover.get("palette") not in palettes:
            raise ProjectError("封面配色无效")
        lines = cover.get("lines")
        if not isinstance(lines, list) or not 1 <= len(lines) <= 4 or not all(isinstance(line, str) and 0 < len(line.strip()) <= 16 for line in lines):
            raise ProjectError("封面标题需 1–4 行，每行 1–16 字")
        tag = str(cover.get("tag", "")).strip()
        if len(tag) > 12:
            raise ProjectError("封面标签最多 12 字")
        post["cover"] = {"tag": tag, "lines": [line.strip() for line in lines], "palette": cover["palette"]}
    if "picks" in body:
        picks = body["picks"]
        if not isinstance(picks, dict) or not all(isinstance(value, list) and all(tool in post["tools"] for tool in value) for value in picks.values()):
            raise ProjectError("对比图选择无效")
        post["picks"] = {str(key): value[:2] for key, value in picks.items()}
    write_json(post_dir / "post.json", post)


def save_scorecard(project: Project, post_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    post_dir = project.post_dir(post_id)
    scorecard = load_json(post_dir / "scorecard.json", {}) or {}
    results = body.get("tool_results")
    if not isinstance(results, dict) or not results:
        raise ProjectError("评分内容为空或格式无效")
    tools = project.post_tools(post_id)
    checks = scorecard.get("checks") or {}
    merged = scorecard.get("tool_results") or {}
    for tool, result in results.items():
        if tool not in tools or not isinstance(result, dict):
            raise ProjectError(f"这一篇没有这个工具：{tool}")
        entry = merged.get(tool) or blank_result()
        values = result.get("checks", entry.get("checks", {}))
        notes = result.get("notes", entry.get("notes", {}))
        if not isinstance(values, dict) or not isinstance(notes, dict) or any(key not in checks for key in list(values) + list(notes)):
            raise ProjectError("检查项无效")
        entry["checks"] = {key: value for key, value in values.items()}
        entry["notes"] = {key: str(value)[:800] for key, value in notes.items()}
        score = result.get("total_score", entry.get("total_score"))
        if score not in (None, "") and (type(score) not in (int, float) or not 1 <= score <= 5):
            raise ProjectError("总评分需在 1–5 之间")
        entry["total_score"] = None if score == "" else score
        for key in ("verdict", "summary", "gut_reaction", "keep_using"):
            if key in result:
                entry[key] = str(result[key] or "")[:800]
        merged[tool] = entry
    scorecard["tool_results"] = merged
    scorecard["status"] = "draft"
    write_json(post_dir / "scorecard.json", scorecard)
    return scorecard


def save_highlights(project: Project, post_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    tool, key = body.get("tool"), body.get("key")
    project.check_scope(post_id, tool)
    project.evidence_spec(post_id, tool, key)
    path = project.post_dir(post_id) / "highlights.json"
    data = load_json(path, {}) or {}
    previous = (data.get(tool) or {}).get(key) or {}
    boxes = body.get("boxes", previous.get("boxes")) or []
    masks = body.get("masks", previous.get("masks")) or []
    clean = []
    clean_masks = []
    if not isinstance(boxes, list) or len(boxes) > 12:
        raise ProjectError("红框最多 12 个")
    for box in boxes:
        try:
            values = {k: round(float(box[k]), 4) for k in ("x", "y", "w", "h")}
        except (KeyError, TypeError, ValueError) as exc:
            raise ProjectError("红框坐标无效") from exc
        if not all(0 <= values[k] <= 1 for k in values) or values["w"] <= 0 or values["h"] <= 0:
            raise ProjectError("红框坐标需在 0–1 之间")
        clean.append({**values, "note": str(box.get("note", ""))[:30]})
    if not isinstance(masks, list) or len(masks) > 20:
        raise ProjectError("隐私遮挡区域最多 20 个")
    for mask in masks:
        try:
            values = {k: round(float(mask[k]), 4) for k in ("x", "y", "w", "h")}
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ProjectError("隐私遮挡坐标无效") from exc
        if (not all(math.isfinite(value) for value in values.values())
                or values["x"] < 0 or values["y"] < 0
                or values["w"] <= 0 or values["h"] <= 0
                or values["x"] + values["w"] > 1
                or values["y"] + values["h"] > 1):
            raise ProjectError("隐私遮挡需完整落在截图 0–1 范围内")
        clean_masks.append(values)
    crop = body.get("crop", previous.get("crop")) or {}
    try:
        y0, y1 = float(crop.get("y0", 0)), float(crop.get("y1", 1))
    except (TypeError, ValueError) as exc:
        raise ProjectError("裁剪范围无效") from exc
    if not (0 <= y0 < y1 <= 1):
        raise ProjectError("裁剪范围无效")
    data.setdefault(tool, {})[key] = {"boxes": clean, "masks": clean_masks, "crop": {"y0": y0, "y1": y1}}
    write_json(path, data)
    return data


def save_cards(project: Project, post_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    cards = body.get("cards")
    if not isinstance(cards, dict):
        raise ProjectError("文字卡格式无效")
    clean: Dict[str, Any] = {}
    for card_id, card in cards.items():
        if card_id == "photo_captions":
            if not isinstance(card, dict):
                raise ProjectError("照片说明格式无效")
            clean[card_id] = {str(k): str(v)[:60] for k, v in card.items()}
            continue
        if not isinstance(card, dict) or not isinstance(card.get("lines", []), list):
            raise ProjectError(f"文字卡 {card_id} 格式无效")
        clean[card_id] = {"title": str(card.get("title", ""))[:40], "lines": [str(line)[:120] for line in card.get("lines", [])][:10]}
    write_json(project.post_dir(post_id) / "cards.json", clean)
    return clean


def decode_upload(body: Dict[str, Any]) -> Tuple[str, bytes]:
    filename = str(body.get("filename") or "upload")
    try:
        data = base64.b64decode(str(body.get("data_base64") or ""), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ProjectError("文件内容无效") from exc
    if not data:
        raise ProjectError("文件是空的")
    return filename, data


def save_photo(project: Project, post_id: str, body: Dict[str, Any]) -> str:
    try:
        index = int(body.get("index"))
    except (TypeError, ValueError) as exc:
        raise ProjectError("照片编号无效") from exc
    if not 1 <= index <= 20:
        raise ProjectError("照片编号需在 1–20")
    _, data = decode_upload(body)
    folder = project.post_dir(post_id) / "photos"
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f".incoming-{index:02d}"
    write_bytes(tmp, data)
    kind = image_kind(tmp)
    if kind not in ("png", "jpeg", "webp"):
        tmp.unlink(missing_ok=True)
        raise ProjectError("照片需为 PNG/JPG/WebP（HEIC 请先放进 inbox 转换）")
    for ext in IMAGE_EXTS:
        existing = folder / f"{index:02d}.{ext}"
        if existing.exists():
            archive = folder / "_replaced"
            archive.mkdir(exist_ok=True)
            existing.rename(archive / f"{index:02d}-{int(time.time())}.{ext}")
    target = folder / f"{index:02d}.{'jpg' if kind == 'jpeg' else kind}"
    tmp.rename(target)
    return project.rel(target)


# ---------------------------------------------------------------------- handler
Route = Tuple[str, "re.Pattern[str]", str]
ROUTES: List[Route] = []


def route(method: str, pattern: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        ROUTES.append((method, re.compile(f"^{pattern}$"), func.__name__))
        return func
    return decorator


POST_ID = r"(?P<post_id>post-\d{2}-[a-z0-9-]+)"


class RadarDashboardHandler(BaseHTTPRequestHandler):
    project_root: Path = PROJECT_ROOT
    server_version = "XHSWorkbench/2.0"

    @property
    def project(self) -> Project:
        return Project(self.project_root)

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("%s - %s", self.address_string(), format % args)

    # ------------------------------------------------------------- plumbing
    def _allowed_origin(self, origin: str) -> bool:
        parsed = urllib.parse.urlparse(origin)
        try:
            return (
                parsed.scheme == "http"
                and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                and parsed.port == self.server.server_port
                and parsed.path in ("", "/")
                and not parsed.username
            )
        except ValueError:
            return False

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and self._allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def send_json(self, data: Any, status: int = 200) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(encoded)

    def send_file(self, path: Path, *, download: bool = False) -> None:
        mime, _ = mimetypes.guess_type(str(path))
        suffix = path.suffix.lower()
        mime = {".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".md": "text/markdown; charset=utf-8", ".json": "application/json; charset=utf-8", ".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8"}.get(suffix, mime or "application/octet-stream")
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if download:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(path.name)}")
        self._cors()
        self.end_headers()
        self.wfile.write(content)

    def read_body(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ProjectError("上传内容太大（上限 80MB）；大文件请用 AirDrop 放进 inbox")
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ProjectError("请求内容不是有效的 JSON") from exc

    def query(self) -> Dict[str, str]:
        return {key: values[-1] for key, values in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}

    def dispatch(self, method: str) -> None:
        path = urllib.parse.urlparse(self.path).path
        path = path.rstrip("/") or "/"
        for route_method, pattern, name in ROUTES:
            if route_method != method:
                continue
            match = pattern.match(path)
            if match:
                try:
                    if method == "POST":
                        with WRITE_LOCK:
                            getattr(self, name)(**match.groupdict())
                    else:
                        getattr(self, name)(**match.groupdict())
                except ProjectError as exc:
                    self.send_json({"error": str(exc)}, 400)
                except RadarUnavailableError as exc:
                    self.send_json({"error": str(exc), "status": "unavailable"}, 502)
                except Exception as exc:  # pragma: no cover - logged for the user
                    logger.exception("Request failed: %s %s", method, path)
                    self.send_json({"error": f"服务器出错：{exc}"}, 500)
                return
        if method == "GET" and not path.startswith("/api/"):
            self.serve_static(path)
            return
        self.send_json({"error": "Not Found", "path": path}, 404)

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin")
        if origin and not self._allowed_origin(origin):
            self.send_json({"error": "Cross-origin requests are not allowed"}, 403)
            return
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        origin = self.headers.get("Origin")
        if (origin and not self._allowed_origin(origin)) or self.headers.get("Sec-Fetch-Site") == "cross-site":
            self.send_json({"error": "Cross-origin writes are not allowed"}, 403)
            return
        self.dispatch("POST")

    # ---------------------------------------------------------------- static
    def serve_static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            return self._serve_under(self.project_root / "web", "index.html")
        if path.startswith("/web/"):
            path = path[len("/web"):]
        for prefix in ("/js/", "/css/", "/vendor/"):
            if path.startswith(prefix):
                return self._serve_under(self.project_root / "web", urllib.parse.unquote(path.lstrip("/")))
        if path.startswith("/assets/"):
            return self.serve_asset(urllib.parse.unquote(path[len("/assets/"):]))
        self.send_json({"error": "Not Found", "path": path}, 404)

    def _serve_under(self, base: Path, relative: str, *, download: bool = False) -> None:
        target = (base / relative)
        try:
            resolved = target.resolve()
            resolved.relative_to(base.resolve())
        except (ValueError, RuntimeError):
            return self.send_json({"error": "Forbidden: Path traversal not allowed"}, 403)
        if resolved != target.absolute():
            return self.send_json({"error": "Symlinks are not public"}, 403)
        if not resolved.is_file():
            return self.send_json({"error": "Not found"}, 404)
        self.send_file(resolved, download=download)

    def serve_asset(self, relative: str) -> None:
        parts = Path(relative).parts
        if ".." in parts:
            return self.send_json({"error": "Forbidden: Path traversal not allowed"}, 403)
        if len(parts) == 2 and parts[0] == "docs" and parts[1].endswith(".md"):
            return self._serve_under(self.project_root / "docs", parts[1])
        if len(parts) == 4 and parts[0] == "posts" and parts[2] in ("images", "photos"):
            post_id, folder, name = parts[1], parts[2], parts[3]
            try:
                self.project.check_post_id(post_id)
            except ProjectError:
                return self.send_json({"error": "Asset not public"}, 403)
            if folder == "photos":
                if Path(name).suffix.lower().lstrip(".") not in IMAGE_EXTS:
                    return self.send_json({"error": "Asset not public"}, 403)
                return self._serve_under(self.project.post_dir(post_id) / "photos", name)
            render = load_json(self.project.post_dir(post_id) / "images" / "render.json", {}) or {}
            listed = {item.get("png") for item in render.get("files", [])} | {item.get("html") for item in render.get("files", [])}
            if name not in listed:
                return self.send_json({"error": "Asset not public"}, 403)
            if render.get("draft") is False:
                readiness = assess_post_readiness(self.project, post_id)
                if not readiness["assets"]["fresh_final"]:
                    return self.send_json({"error": "这组终版图片对应的复核已失效，请重新复核并生成"}, 409)
            return self._serve_under(self.project.post_dir(post_id) / "images", name, download=self.query().get("download") == "1")
        self.send_json({"error": "Asset not public", "asset": relative}, 403)

    # ------------------------------------------------------------- general
    @route("GET", r"/api/status")
    def get_status(self) -> None:
        project = self.project
        posts = project.list_posts()
        ready = sum(1 for post_id in posts if assess_post_readiness(project, post_id)["publishable"])
        self.send_json({
            "status": "ok",
            "server": "科技试吃员 · 起号工作台",
            "posts": len(posts),
            "publishable_posts": ready,
            "radar": {"mode": "leads", "live_sources": ["manual", "appstore", "official"], "demo_available": True},
            "monitoring_sources": RadarScanner(project.root / "scripts" / "radar_sources.json").get_configured_sources(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })

    @route("GET", r"/api/config")
    def get_config(self) -> None:
        project = self.project
        topics = [{key: topic.get(key) for key in ("id", "slug", "name", "title", "format", "week", "audience", "tools", "min_tools", "tools_editable", "requires_verified_posts")} for topic in project.topics()]
        self.send_json({"brand": project.brand(), "tools": project.tools(), "topics": topics})

    @route("GET", r"/api/prompts")
    def get_prompts(self) -> None:
        folder = self.project_root / "harness" / "prompts"
        prompts = [{"filename": path.name, "topic_name": path.stem, "path": f"harness/prompts/{path.name}", "content": path.read_text(encoding="utf-8")} for path in sorted(folder.glob("*.md"))] if folder.is_dir() else []
        self.send_json({"status": "success", "count": len(prompts), "prompts": prompts})

    # ---------------------------------------------------------------- posts
    @route("GET", r"/api/posts")
    def get_posts(self) -> None:
        project = self.project
        self.send_json({"posts": [post_summary(project, post_id) for post_id in project.list_posts()]})

    @route("POST", r"/api/posts")
    def create_post_route(self) -> None:
        body = self.read_body()
        project = self.project
        post_id = create_post(project, str(body.get("topic_id", "")).zfill(2), tools=body.get("tools") or None, slug=body.get("slug") or None)
        ops.attach_post(project, project.load_post(post_id)["topic_id"], post_id)
        self.send_json({"post_id": post_id, "detail": post_detail(project, post_id)}, 201)

    @route("GET", rf"/api/posts/{POST_ID}")
    def get_post(self, post_id: str) -> None:
        if not self.project.post_exists(post_id):
            return self.send_json({"error": "篇目不存在"}, 404)
        self.send_json(post_detail(self.project, post_id))

    def _require(self, post_id: str) -> Project:
        project = self.project
        if not project.post_exists(post_id):
            raise ProjectError("篇目不存在")
        return project

    @route("POST", rf"/api/posts/{POST_ID}/settings")
    def post_settings(self, post_id: str) -> None:
        project = self._require(post_id)
        update_settings(project, post_id, self.read_body())
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/scorecard")
    def post_scorecard(self, post_id: str) -> None:
        project = self._require(post_id)
        save_scorecard(project, post_id, self.read_body())
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/copy")
    def post_copy(self, post_id: str) -> None:
        project = self._require(post_id)
        text = self.read_body().get("text")
        if not isinstance(text, str) or len(text) > 60000:
            raise ProjectError("文案内容无效")
        write_text(project.post_dir(post_id) / "copy.md", text.replace("\r\n", "\n"))
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/cards")
    def post_cards(self, post_id: str) -> None:
        project = self._require(post_id)
        save_cards(project, post_id, self.read_body())
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/highlights")
    def post_highlights(self, post_id: str) -> None:
        project = self._require(post_id)
        save_highlights(project, post_id, self.read_body())
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/evidence/text")
    def post_evidence_text(self, post_id: str) -> None:
        project = self._require(post_id)
        body = self.read_body()
        save_text(project, post_id, body.get("scope", ""), body.get("key", ""), body.get("text"))
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/evidence/file")
    def post_evidence_file(self, post_id: str) -> None:
        project = self._require(post_id)
        body = self.read_body()
        filename, data = decode_upload(body)
        store_bytes(project, post_id, body.get("scope", ""), body.get("key", ""), filename, data)
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/evidence/meta")
    def post_evidence_meta(self, post_id: str) -> None:
        project = self._require(post_id)
        body = self.read_body()
        set_metadata(project, post_id, body.get("tool", ""), body.get("fields") or {})
        self.send_json(post_detail(project, post_id))

    @route("GET", rf"/api/posts/{POST_ID}/evidence-file")
    def get_evidence_file(self, post_id: str) -> None:
        project = self._require(post_id)
        params = self.query()
        scope = project.check_scope(post_id, params.get("scope", ""))
        spec = project.evidence_spec(post_id, scope, params.get("key", ""))
        manifest = load_manifest(project, post_id)
        relative = (manifest["shared"].get(spec["key"]) if scope == SHARED_SCOPE else manifest["tools"][scope]["files"].get(spec["key"]))
        if not relative:
            return self.send_json({"error": "还没有录入"}, 404)
        path = project.resolve_inside(relative, project.post_dir(post_id) / "evidence" / scope)
        if not path.is_file():
            return self.send_json({"error": "文件不存在"}, 404)
        self.send_file(path)

    @route("GET", rf"/api/posts/{POST_ID}/inbox")
    def get_inbox(self, post_id: str) -> None:
        project = self._require(post_id)
        self.send_json({"inbox": list_inbox(project, post_id)})

    @route("GET", rf"/api/posts/{POST_ID}/inbox-file")
    def get_inbox_file(self, post_id: str) -> None:
        project = self._require(post_id)
        name = self.query().get("name", "")
        if "/" in name or "\\" in name or name.startswith("."):
            raise ProjectError("文件名无效")
        self._serve_under(project.post_dir(post_id) / "inbox", name)

    @route("POST", rf"/api/posts/{POST_ID}/inbox/assign")
    def post_inbox_assign(self, post_id: str) -> None:
        project = self._require(post_id)
        body = self.read_body()
        assign_inbox_file(project, post_id, body.get("name", ""), body.get("scope", ""), body.get("key", ""))
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/inbox/auto")
    def post_inbox_auto(self, post_id: str) -> None:
        project = self._require(post_id)
        assigned = auto_assign(project, post_id)
        self.send_json({"assigned": assigned, "detail": post_detail(project, post_id)})

    @route("POST", rf"/api/posts/{POST_ID}/photo")
    def post_photo(self, post_id: str) -> None:
        project = self._require(post_id)
        save_photo(project, post_id, self.read_body())
        self.send_json(post_detail(project, post_id))

    @route("POST", rf"/api/posts/{POST_ID}/review")
    def post_review(self, post_id: str) -> None:
        project = self._require(post_id)
        body = self.read_body()
        if body.get("confirm") is not True:
            raise ProjectError("需要确认已逐条对照原文核对")
        result = review_post(project, post_id, str(body.get("reviewed_by") or ""), body.get("test_date") or None)
        status = 409 if result["status"] == "blocked" else 200
        self.send_json({**result, "detail": post_detail(project, post_id)}, status)

    @route("POST", rf"/api/posts/{POST_ID}/render")
    def post_render(self, post_id: str) -> None:
        project = self._require(post_id)
        result = render_post(project, post_id)
        status = 200 if result["status"] == "rendered" else 500
        self.send_json({"status": result["status"], "draft": result["draft"], "engine": result["engine"], "detail": post_detail(project, post_id)}, status)

    @route("POST", rf"/api/posts/{POST_ID}/handoff")
    def post_handoff(self, post_id: str) -> None:
        project = self._require(post_id)
        path = write_handoff(project, post_id)
        self.send_json({"path": project.rel(path), "text": path.read_text(encoding="utf-8")})

    @route("POST", rf"/api/posts/{POST_ID}/published")
    def post_published(self, post_id: str) -> None:
        project = self._require(post_id)
        readiness = assess_post_readiness(project, post_id)
        if not readiness["publishable"]:
            raise ProjectError("发布包还没放行，不能标记为已发布")
        slot = ops.mark_published(project, post_id, str(self.read_body().get("published_at") or ""))
        self.send_json({"slot": slot})

    @route("GET", rf"/api/posts/{POST_ID}/package")
    def get_package(self, post_id: str) -> None:
        project = self._require(post_id)
        readiness = assess_post_readiness(project, post_id)
        if not readiness["publishable"]:
            return self.send_json({"error": "发布包还没放行", "blockers": readiness["blockers"]}, 409)
        detail = post_detail(project, post_id)
        parsed = detail["copy_parsed"]
        self.send_json({"title": parsed["titles"][0], "body": parsed["body"], "tags": parsed["tags"], "pin": parsed["pin"], "images": detail["images"]["files"], "reminders": detail["lint"]["reminders"]})

    # -------------------------------------------------------------- ops data
    @route("GET", r"/api/calendar")
    def get_calendar(self) -> None:
        project = self.project
        data = ops.load_calendar(project)
        cache: Dict[str, Any] = {}
        for week in data["weeks"]:
            for slot in week["slots"]:
                post_id = slot.get("post_id")
                readiness = None
                if post_id and project.post_exists(post_id):
                    readiness = cache.setdefault(post_id, assess_post_readiness(project, post_id))
                slot["display_status"] = ops.derived_status(readiness, slot)
        self.send_json(data)

    @route("POST", r"/api/calendar")
    def post_calendar(self) -> None:
        body = self.read_body()
        data = body.get("calendar")
        if isinstance(data, dict):
            for week in data.get("weeks", []):
                for slot in week.get("slots", []):
                    if isinstance(slot, dict):
                        slot.pop("display_status", None)
        self.send_json(ops.save_calendar(self.project, data))

    @route("GET", r"/api/metrics")
    def get_metrics(self) -> None:
        self.send_json({"rows": ops.load_metrics(self.project)})

    @route("POST", r"/api/metrics")
    def post_metrics(self) -> None:
        row = ops.upsert_metric(self.project, self.read_body().get("row") or {})
        self.send_json({"row": row, "rows": ops.load_metrics(self.project)})

    @route("POST", r"/api/reviews/weekly")
    def post_weekly_review(self) -> None:
        body = self.read_body()
        week = body.get("week")
        if week not in (None, "") and (not isinstance(week, int) or week < 1):
            raise ProjectError("周数无效")
        path = write_review(self.project, week or None)
        self.send_json({"path": self.project.rel(path), "text": path.read_text(encoding="utf-8")})

    @route("GET", r"/api/account")
    def get_account(self) -> None:
        self.send_json(ops.load_account(self.project))

    @route("POST", r"/api/account")
    def post_account(self) -> None:
        self.send_json(ops.save_account(self.project, self.read_body()))

    @route("GET", r"/api/requests")
    def get_requests(self) -> None:
        self.send_json({"rows": ops.load_requests(self.project)})

    @route("POST", r"/api/requests")
    def post_requests(self) -> None:
        ops.add_request(self.project, self.read_body())
        self.send_json({"rows": ops.load_requests(self.project)})

    @route("POST", r"/api/requests/status")
    def post_request_status(self) -> None:
        body = self.read_body()
        ops.update_request(self.project, str(body.get("request", "")), str(body.get("status", "")))
        self.send_json({"rows": ops.load_requests(self.project)})

    @route("GET", r"/api/benchmarks")
    def get_benchmarks(self) -> None:
        self.send_json({"rows": ops.load_benchmarks(self.project)})

    @route("POST", r"/api/benchmarks")
    def post_benchmarks(self) -> None:
        ops.add_benchmark(self.project, self.read_body())
        self.send_json({"rows": ops.load_benchmarks(self.project)})

    # ----------------------------------------------------------------- leads
    @route("GET", r"/api/leads")
    def get_leads(self) -> None:
        state = load_state(self.project)
        self.send_json({"rows": ops.load_leads(self.project), "appstore": state["appstore"], "official": {key: {"checked_at": value.get("checked_at")} for key, value in state["official"].items()}})

    @route("POST", r"/api/leads")
    def post_leads(self) -> None:
        ops.add_lead(self.project, self.read_body())
        self.send_json({"rows": ops.load_leads(self.project)})

    @route("POST", r"/api/leads/(?P<lead_id>L\d{4})")
    def post_lead_update(self, lead_id: str) -> None:
        ops.update_lead(self.project, lead_id, self.read_body())
        self.send_json({"rows": ops.load_leads(self.project)})

    @route("POST", r"/api/leads/appstore-resolve")
    def post_appstore_resolve(self) -> None:
        self.send_json(appstore_resolve(self.project))

    @route("POST", r"/api/leads/appstore-confirm")
    def post_appstore_confirm(self) -> None:
        body = self.read_body()
        try:
            track_id = int(body.get("track_id"))
        except (TypeError, ValueError) as exc:
            raise ProjectError("App 编号无效") from exc
        self.send_json(appstore_confirm(self.project, str(body.get("tool", "")), track_id))

    @route("POST", r"/api/leads/appstore-check")
    def post_appstore_check(self) -> None:
        self.send_json(appstore_check(self.project))

    @route("POST", r"/api/leads/official-check")
    def post_official_check(self) -> None:
        self.send_json(official_check(self.project))

    @route("POST", r"/api/radar/scan")
    def post_radar_scan(self) -> None:
        body = self.read_body()
        if body.get("mock") is not True:
            return self.send_json({"status": "unavailable", "mode": "live", "message": "真实线索请在“线索”页运行 App Store 或官方更新页检查；这里只提供演示数据", "action_cards": [], "detected_events": 0, "count": 0}, 501)
        mock = body.get("mock_data")
        if mock is not None and not isinstance(mock, dict):
            raise ProjectError("mock_data must be an object")
        cards = RadarScanner(self.project_root / "scripts" / "radar_sources.json").scan(mock if mock is not None else DEFAULT_MOCK_DATA, self.project_root / "logs" / "radar_actions" / "demo")
        self.send_json({"status": "success", "mode": "demo", "message": "演示数据生成的候选题；未核实原始来源及当前账号可用性", "detected_events": len(cards), "action_cards": cards, "count": len(cards)})

    @route("GET", r"/api/radar/cards")
    def get_radar_cards(self) -> None:
        folder = self.project_root / "logs" / "radar_actions" / "demo"
        cards = []
        if folder.is_dir():
            for path in sorted(folder.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
                content = path.read_text(encoding="utf-8")
                cards.append({"filename": path.name, "path": f"logs/radar_actions/demo/{path.name}", "title": content.splitlines()[0].lstrip("# ").strip() if content else path.stem, "content": content, "mode": "demo"})
        self.send_json({"status": "success", "count": len(cards), "cards": cards})

    # ---------------------------------------------------------------- compat
    @route("GET", r"/api/post/01")
    def get_post_01(self) -> None:
        project = self._require(POST_01)
        detail = post_detail(project, POST_01)
        self.send_json({"status": "success", "post_id": POST_01, **detail})

    @route("POST", r"/api/post/01/scorecard")
    def post_post_01_scorecard(self) -> None:
        project = self._require(POST_01)
        save_scorecard(project, POST_01, self.read_body())
        self.send_json(post_detail(project, POST_01))


def create_request_handler(project_root: Optional[Union[str, Path]] = None) -> type:
    root = Path(project_root).resolve() if project_root else PROJECT_ROOT

    class BoundHandler(RadarDashboardHandler):
        project_root = root

    return BoundHandler


class RadarDashboardServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, project_root: Optional[Union[str, Path]] = None):
        self.host = host
        self.requested_port = port
        self.project_root = Path(project_root).resolve() if project_root else PROJECT_ROOT
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.port = port
        self.is_running = False

    def start(self) -> "RadarDashboardServer":
        if self.is_running:
            return self
        self.server = ThreadingHTTPServer((self.host, self.requested_port), create_request_handler(self.project_root))
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.is_running = True
        return self

    def stop(self) -> None:
        if self.is_running and self.server:
            self.server.shutdown()
            self.server.server_close()
            self.is_running = False
            if self.thread:
                self.thread.join(timeout=2.0)

    close = stop

    def __enter__(self) -> "RadarDashboardServer":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass

    def get_test_client(self) -> TestClient:
        if not self.is_running:
            self.start()
        return TestClient(f"http://{self.host}:{self.port}")


def main() -> int:
    parser = argparse.ArgumentParser(description="科技试吃员 · 起号工作台（本机服务）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    server = RadarDashboardServer(host=args.host, port=args.port).start()
    print(f"工作台已启动：http://{server.host}:{server.port}  （Ctrl+C 退出）")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
