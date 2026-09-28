"""Lead sources: App Store versions, official pages, demo cards and topic matching."""
import json

import pytest

from scripts import ops
from scripts.topic_matcher import match_topic_and_generate_card
from scripts.xhs_radar import DEFAULT_MOCK_DATA, RadarScanner, RadarUnavailableError, appstore_check, appstore_confirm, appstore_resolve, load_state, official_check


class FakeStore:
    def __init__(self):
        self.version = "3.0"
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        if "/search?" in url:
            return json.dumps({"results": [{"trackId": 111, "trackName": "Kimi 智能助手", "sellerName": "Moonshot", "version": self.version}]}).encode()
        return json.dumps({"results": [{"trackId": 111, "version": self.version, "releaseNotes": "新增 PPT 导出", "currentVersionReleaseDate": "2026-09-27T00:00:00Z", "trackViewUrl": "https://apps.apple.com/cn/app/id111"}]}).encode()


def test_appstore_resolve_confirm_check_and_change(project):
    fetch = FakeStore()
    with pytest.raises(RadarUnavailableError):
        appstore_check(project, fetch=fetch)
    resolved = appstore_resolve(project, fetch=fetch)
    assert resolved["candidates"]["kimi"][0]["track_id"] == 111
    assert all("country=cn" in url for url in fetch.calls)
    appstore_confirm(project, "kimi", 111)
    with pytest.raises(Exception):
        appstore_confirm(project, "kimi", 999)
    first = appstore_check(project, fetch=fetch)
    assert first["baseline"] == ["kimi"] and first["changes"] == []
    fetch.version = "3.1"
    second = appstore_check(project, fetch=fetch)
    assert len(second["changes"]) == 1
    lead = ops.load_leads(project)[0]
    assert lead["source"] == "appstore" and lead["status"] == "待核实" and "3.1" in lead["title"]
    assert load_state(project)["appstore"]["apps"]["kimi"]["version"] == "3.1"


def test_unreachable_sources_are_reported_not_faked(project):
    def down(url):
        raise RadarUnavailableError("无法访问")
    result = appstore_resolve(project, fetch=down)
    assert result["errors"] and not any(result["candidates"].values())
    official = official_check(project, fetch=down)
    assert official["errors"] and ops.load_leads(project) == []


def test_official_page_baseline_then_change(project):
    pages = {"text": "<html><body><h1>Change Log</h1><p>2026-09-01 旧条目</p></body></html>"}
    fetch = lambda url: pages["text"].encode()
    assert official_check(project, fetch=fetch)["baseline"] == ["deepseek_updates"]
    pages["text"] = pages["text"].replace("</body>", "<p>2026-09-27 新模型上线</p></body>")
    result = official_check(project, fetch=fetch)
    assert len(result["changes"]) == 1
    assert "新模型上线" in ops.load_leads(project)[0]["description"]


def test_demo_scan_requires_explicit_mock_and_is_labeled(project):
    scanner = RadarScanner(project.root / "scripts" / "radar_sources.json")
    with pytest.raises(RadarUnavailableError):
        scanner.scan(None)
    cards = scanner.scan(DEFAULT_MOCK_DATA, project.root / "logs" / "demo")
    assert cards and all(card["mode"] == "demo" for card in cards)
    written = list((project.root / "logs" / "demo").glob("*.md"))
    assert written and all("演示数据" in path.read_text(encoding="utf-8") for path in written)
    assert "arena" not in scanner.get_configured_sources()


@pytest.mark.parametrize("title, topic", [
    ("Kimi App 更新：PPT 助手支持导出 PPTX", "02"),
    ("千问上线视频理解功能", "11"),
    ("可灵新版文生视频", "10"),
    ("有人说豆包的会议纪要能区分说话人了", "07"),
    ("讯飞听见支持录音转写", "07"),
    ("随便说点什么", "unmatched"),
    ("appointment reminder", "unmatched"),
])
def test_topic_matching(title, topic):
    assert match_topic_and_generate_card({"title": title})["topic_id"] == topic


def test_matched_card_uses_topic_tools_and_titles():
    card = match_topic_and_generate_card({"title": "WPS 表格公式助手上线"})
    assert card["topic_id"] == "05"
    assert card["comparison_group"] == ["DeepSeek", "豆包", "WPS AI"]
    assert len(card["hook_title"]) <= 20
    assert match_topic_and_generate_card({"title": "x", "category": "arena_anonymous"})["topic_id"] == "unmatched"
