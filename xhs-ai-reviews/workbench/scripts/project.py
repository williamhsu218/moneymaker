"""Shared project paths, config loaders and small file helpers.

Everything that reads brand, tool, topic or post files goes through here so
that the dashboard, CLI scripts and tests agree on one layout:

    config/brand.json        account name, voice, palettes
    config/tools.json        tool ids, display names, links
    harness/topics.json      the 12 topic definitions (single source of truth)
    posts/<post_id>/         one workspace per post
    ops/                     calendar, metrics, account audit, leads
"""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POST_ID_RE = re.compile(r"^post-(\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*$")
TOOL_ID_RE = re.compile(r"^[a-z0-9_]{2,40}$")
SHARED_SCOPE = "shared"

IMAGE_SIGNATURES = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "webp": (b"RIFF",),
}
IMAGE_EXTS = ("png", "jpg", "jpeg", "webp")
HEIC_EXTS = ("heic", "heif")


class ProjectError(ValueError):
    """Raised for invalid ids, paths or payloads (maps to HTTP 400)."""


def load_json(path: Union[str, Path], default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return default


def write_json(path: Union[str, Path], data: Any) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def write_text(path: Union[str, Path], text: str) -> None:
    """Atomic text write: a crash never leaves a half-written file."""
    write_bytes(path, text.encode("utf-8"))


def write_bytes(path: Union[str, Path], data: bytes) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def sha256_file(path: Union[str, Path]) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def valid_date(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def valid_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def image_kind(path: Path) -> Optional[str]:
    """Return the real image type from the file signature, not the name."""
    try:
        with path.open("rb") as handle:
            head = handle.read(16)
    except OSError:
        return None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    if head[4:12] in (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1", b"ftypmsf1", b"ftypheim", b"ftypheis"):
        return "heic"
    return None


def image_size(path: Path) -> Optional[tuple]:
    """Read pixel size from PNG/JPEG/WebP headers without extra libraries."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = int.from_bytes(data[index + 2:index + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height = int.from_bytes(data[index + 5:index + 7], "big")
                width = int.from_bytes(data[index + 7:index + 9], "big")
                return width, height
            index += 2 + length
        return None
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            return 1 + int.from_bytes(data[24:27], "little"), 1 + int.from_bytes(data[27:30], "little")
        if chunk == b"VP8 " and len(data) >= 30:
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
        if chunk == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    return None


class Project:
    """Loader bound to one project root (tests use disposable copies)."""

    def __init__(self, root: Optional[Union[str, Path]] = None):
        self.root = Path(root).resolve() if root else PROJECT_ROOT
        self.config_dir = self.root / "config"
        self.posts_dir = self.root / "posts"
        self.ops_dir = self.root / "ops"
        self.harness_dir = self.root / "harness"

    # ------------------------------------------------------------------ config
    def brand(self) -> Dict[str, Any]:
        return load_json(self.config_dir / "brand.json", {}) or {}

    def tools(self) -> List[Dict[str, Any]]:
        data = load_json(self.config_dir / "tools.json", {}) or {}
        return [tool for tool in data.get("tools", []) if isinstance(tool, dict) and tool.get("id")]

    def tool_map(self) -> Dict[str, Dict[str, Any]]:
        return {tool["id"]: tool for tool in self.tools()}

    def tool_name(self, tool_id: str) -> str:
        tool = self.tool_map().get(tool_id)
        return tool.get("display_name", tool_id) if tool else tool_id

    def topics_doc(self) -> Dict[str, Any]:
        return load_json(self.harness_dir / "topics.json", {}) or {}

    def topics(self) -> List[Dict[str, Any]]:
        return [topic for topic in self.topics_doc().get("topics", []) if isinstance(topic, dict)]

    def topic(self, topic_id: str) -> Dict[str, Any]:
        for topic in self.topics():
            if topic.get("id") == topic_id:
                return topic
        raise ProjectError(f"未知选题：{topic_id}")

    # ------------------------------------------------------------------- posts
    def check_post_id(self, post_id: str) -> str:
        if not isinstance(post_id, str) or not POST_ID_RE.match(post_id):
            raise ProjectError(f"无效的篇目编号：{post_id!r}")
        return post_id

    def post_dir(self, post_id: str) -> Path:
        return self.posts_dir / self.check_post_id(post_id)

    def post_exists(self, post_id: str) -> bool:
        try:
            return (self.post_dir(post_id) / "post.json").is_file()
        except ProjectError:
            return False

    def list_posts(self) -> List[str]:
        if not self.posts_dir.is_dir():
            return []
        return sorted(
            path.name for path in self.posts_dir.iterdir()
            if path.is_dir() and POST_ID_RE.match(path.name) and (path / "post.json").is_file()
        )

    def load_post(self, post_id: str) -> Dict[str, Any]:
        post = load_json(self.post_dir(post_id) / "post.json")
        if not isinstance(post, dict):
            raise ProjectError(f"篇目不存在：{post_id}")
        return post

    def post_topic(self, post_id: str) -> Dict[str, Any]:
        return self.topic(self.load_post(post_id).get("topic_id", ""))

    def post_tools(self, post_id: str) -> List[str]:
        tools = self.load_post(post_id).get("tools") or []
        return [tool for tool in tools if isinstance(tool, str)]

    def check_scope(self, post_id: str, scope: str) -> str:
        """A scope is a tool id used by this post, or the shared folder."""
        if scope == SHARED_SCOPE:
            return scope
        if not isinstance(scope, str) or not TOOL_ID_RE.match(scope) or scope not in self.post_tools(post_id):
            raise ProjectError(f"这一篇没有这个工具：{scope!r}")
        return scope

    def evidence_spec(self, post_id: str, scope: str, key: str) -> Dict[str, Any]:
        topic = self.post_topic(post_id)
        bucket = "shared" if scope == SHARED_SCOPE else "per_tool"
        for spec in (topic.get("evidence") or {}).get(bucket, []):
            if spec.get("key") == key:
                return spec
        raise ProjectError(f"这一期没有这项证据：{key!r}")

    def rel(self, path: Path) -> str:
        return str(Path(path).resolve().relative_to(self.root)).replace(os.sep, "/")

    def resolve_inside(self, relative: str, base: Path) -> Path:
        """Resolve a project-relative path and require it to stay under base."""
        if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
            raise ProjectError("路径无效")
        full = (self.root / relative).resolve()
        try:
            full.relative_to(base.resolve())
        except ValueError as exc:
            raise ProjectError("路径超出允许范围") from exc
        return full


def fill_brand_tokens(text: str, brand: Dict[str, Any]) -> str:
    return (
        str(text)
        .replace("{{opener}}", brand.get("opener", ""))
        .replace("{{closer}}", brand.get("closer", ""))
        .replace("{{account_name}}", brand.get("account_name", ""))
    )


def unique(items: Iterable[str]) -> List[str]:
    seen: List[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen
