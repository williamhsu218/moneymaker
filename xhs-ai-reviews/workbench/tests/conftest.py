"""Shared fixtures: every test works on a disposable copy of the project."""
from __future__ import annotations

import re
import shutil
import struct
import sys
import zlib
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.project import Project  # noqa: E402


def make_png(width: int = 60, height: int = 120, rgb=(240, 240, 240)) -> bytes:
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


FAKE_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 200 + b"\xff\xd9"
FAKE_HEIC = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 200


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    for folder in ("config", "harness", "web", "docs"):
        shutil.copytree(ROOT_DIR / folder, tmp_path / folder)
    (tmp_path / "scripts").mkdir()
    shutil.copy2(ROOT_DIR / "scripts" / "radar_sources.json", tmp_path / "scripts" / "radar_sources.json")
    (tmp_path / "posts").mkdir()
    return tmp_path


@pytest.fixture
def project(project_root: Path) -> Project:
    return Project(project_root)


def fill_value(check: dict):
    kind = check.get("type", "boolean")
    if kind == "boolean":
        return "pass"
    if kind == "enum":
        return check["options"][0]
    if kind == "number":
        return check.get("min", 1) if check.get("min", 1) >= 1 else 1
    return "合成测试文字"


def complete_post(project: Project, post_id: str, *, image: bytes = None) -> None:
    """Fill every required piece of a post with synthetic content (tests only)."""
    from scripts.evidence_intake import save_text, set_metadata, store_bytes
    from scripts.project import load_json, write_json, write_text

    image = image or make_png()
    topic = project.post_topic(post_id)
    for tool in project.post_tools(post_id):
        set_metadata(project, post_id, tool, {"model": "fixture model", "version": "1.0", "platform": "iOS App", "settings": "默认", "free_tier": "免费版", "tested_at": "2026-09-28T20:30:00+08:00"})
        for spec in topic["evidence"]["per_tool"]:
            if spec["kind"] == "text":
                save_text(project, post_id, tool, spec["key"], f"合成测试回答（{tool} / {spec['key']}），仅用于自动化测试。")
            elif spec["kind"] == "image":
                store_bytes(project, post_id, tool, spec["key"], "shot.png", image)
            elif spec.get("required", True):
                store_bytes(project, post_id, tool, spec["key"], f"file.{spec['exts'][0]}", b"synthetic file")
    for spec in topic["evidence"].get("shared", []):
        if spec["kind"] == "text":
            save_text(project, post_id, "shared", spec["key"], "合成共用证据：只用于自动化测试，不是真实材料。")
        elif spec["kind"] == "image":
            store_bytes(project, post_id, "shared", spec["key"], "shared.png", image)
        else:
            store_bytes(project, post_id, "shared", spec["key"], f"shared.{spec['exts'][0]}", b"synthetic file")
    post_dir = project.post_dir(post_id)
    scorecard = load_json(post_dir / "scorecard.json")
    for tool in project.post_tools(post_id):
        result = scorecard["tool_results"][tool]
        for check_id, check in scorecard["checks"].items():
            result["checks"][check_id] = fill_value(check)
            if check.get("type", "boolean") == "boolean":
                result["notes"][check_id] = "原文如实保留了状态"
        result.update({"total_score": 4, "verdict": "改一处就能用", "summary": "合成测试结论", "gut_reaction": "还行", "keep_using": "会"})
    write_json(post_dir / "scorecard.json", scorecard)
    copy = (post_dir / "copy.md").read_text(encoding="utf-8")
    copy = re.sub(r"【[^】]*】", "合成", copy).replace("- [ ]", "- [x]")
    write_text(post_dir / "copy.md", copy)
    cards = load_json(post_dir / "cards.json", {})
    for card_id, card in cards.items():
        if card_id != "photo_captions":
            card["title"] = re.sub(r"【[^】]*】", "合成", card.get("title", ""))
            card["lines"] = [re.sub(r"【[^】]*】", "合成", line) for line in card.get("lines", [])]
    write_json(post_dir / "cards.json", cards)


def fake_export(pairs, width=1080, height=1440):
    """Stand-in PNG exporter so gate tests do not need a browser."""
    for _, dest in pairs:
        Path(dest).write_bytes(make_png(12, 16))
    return [True] * len(pairs), "fake"
