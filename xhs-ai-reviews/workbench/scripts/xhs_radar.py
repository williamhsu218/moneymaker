#!/usr/bin/env python3
"""New-release leads from sources that work on a mainland network.

Three sources feed ops/leads.csv; every lead starts as “待核实” and only
becomes a post after you confirm the feature works in your own account:

  1. manual     — you paste a link and one sentence (the main entry)
  2. appstore   — App Store (China) version and release notes of the apps in
                  config/tools.json, via Apple's public iTunes Search/Lookup API
  3. official   — official changelog pages listed in scripts/radar_sources.json

The Arena / Reddit / X layer of the earlier design was removed: it is hard to
reach from the mainland, anonymous models and rumors cannot be verified, and
it did not match the “only test apps people in China can use” rule.

    python scripts/xhs_radar.py --appstore-resolve   # find App IDs (confirm in the dashboard)
    python scripts/xhs_radar.py --appstore-check     # compare versions, add leads
    python scripts/xhs_radar.py --official-check     # diff official pages, add leads
    python scripts/xhs_radar.py --scan --mock        # demo cards only, clearly labeled
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import html as html_lib
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Union
import urllib.error
import urllib.parse
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops import add_lead
from scripts.project import Project, ProjectError, load_json, now_iso, write_json, write_text
from scripts.topic_matcher import match_topic_and_generate_card

DEFAULT_CONFIG_PATH = Path(__file__).parent / "radar_sources.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) XHS-Taster-Radar/2.0"
Fetcher = Callable[[str], bytes]


class RadarUnavailableError(RuntimeError):
    """A live source could not be reached; never fall back to demo data."""


def http_get(url: str, timeout: float = 15.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(3 * 1024 * 1024)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise RadarUnavailableError(f"无法访问 {urllib.parse.urlparse(url).netloc}：{exc}") from exc


def load_config(project: Project) -> Dict[str, Any]:
    return load_json(project.root / "scripts" / "radar_sources.json", {}) or load_json(DEFAULT_CONFIG_PATH, {}) or {}


def state_path(project: Project) -> Path:
    return project.ops_dir / "radar_state.json"


def load_state(project: Project) -> Dict[str, Any]:
    state = load_json(state_path(project), {}) or {}
    state.setdefault("appstore", {"apps": {}, "candidates": {}})
    state.setdefault("official", {})
    return state


# -------------------------------------------------------------------- appstore
def appstore_resolve(project: Project, fetch: Fetcher = http_get) -> Dict[str, Any]:
    """Search the CN App Store for each tool name; store candidates to confirm."""
    config = (load_config(project).get("sources") or {}).get("appstore") or {}
    base = config.get("search_url", "https://itunes.apple.com/search")
    country = config.get("country", "cn")
    state = load_state(project)
    errors = {}
    for tool in project.tools():
        term = tool.get("appstore_term")
        if not term or tool["id"] in state["appstore"]["apps"]:
            continue
        url = f"{base}?{urllib.parse.urlencode({'term': term, 'country': country, 'entity': 'software', 'limit': 5})}"
        try:
            payload = json.loads(fetch(url).decode("utf-8"))
        except RadarUnavailableError as exc:
            errors[tool["id"]] = str(exc)
            continue
        except ValueError:
            errors[tool["id"]] = "返回内容不是 JSON"
            continue
        state["appstore"]["candidates"][tool["id"]] = [
            {"track_id": item.get("trackId"), "name": item.get("trackName"), "seller": item.get("sellerName"), "version": item.get("version")}
            for item in payload.get("results", []) if item.get("trackId")
        ]
    write_json(state_path(project), state)
    return {"candidates": state["appstore"]["candidates"], "errors": errors}


def appstore_confirm(project: Project, tool_id: str, track_id: int) -> Dict[str, Any]:
    if tool_id not in project.tool_map():
        raise ProjectError("未知工具")
    state = load_state(project)
    options = state["appstore"]["candidates"].get(tool_id, [])
    chosen = next((item for item in options if item.get("track_id") == track_id), None)
    if chosen is None:
        raise ProjectError("请从候选列表里选择")
    state["appstore"]["apps"][tool_id] = {"track_id": track_id, "name": chosen.get("name"), "seller": chosen.get("seller"), "version": None, "release_date": None, "checked_at": None}
    write_json(state_path(project), state)
    return state["appstore"]["apps"][tool_id]


def appstore_check(project: Project, fetch: Fetcher = http_get) -> Dict[str, Any]:
    """Look up confirmed apps; a changed version becomes a “待核实” lead."""
    config = (load_config(project).get("sources") or {}).get("appstore") or {}
    base = config.get("lookup_url", "https://itunes.apple.com/lookup")
    country = config.get("country", "cn")
    state = load_state(project)
    apps = state["appstore"]["apps"]
    if not apps:
        raise RadarUnavailableError("还没有确认任何 App 的 App Store 编号：先运行“查找 App 编号”，再在线索页确认")
    ids = ",".join(str(item["track_id"]) for item in apps.values())
    payload = json.loads(fetch(f"{base}?{urllib.parse.urlencode({'id': ids, 'country': country})}").decode("utf-8"))
    by_id = {item.get("trackId"): item for item in payload.get("results", [])}
    changes, baseline = [], []
    for tool_id, info in apps.items():
        item = by_id.get(info["track_id"])
        if not item:
            continue
        version, notes = item.get("version"), (item.get("releaseNotes") or "").strip()
        released = item.get("currentVersionReleaseDate")
        if info.get("version") is None:
            baseline.append(tool_id)
        elif version != info.get("version"):
            lead = add_lead(project, {
                "title": f"{project.tool_name(tool_id)} App 更新到 {version}",
                "url": item.get("trackViewUrl", ""),
                "description": notes[:600],
                "tool": tool_id,
                "note": f"上个版本 {info.get('version')}；发布于 {released}",
            }, source="appstore")
            changes.append(lead)
        info.update({"version": version, "release_date": released, "release_notes": notes[:2000], "checked_at": now_iso()})
    write_json(state_path(project), state)
    return {"changes": changes, "baseline": baseline, "checked": len(apps)}


# -------------------------------------------------------------------- official
def page_text(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", "\n", text)
    lines = [html_lib.unescape(line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def official_check(project: Project, fetch: Fetcher = http_get) -> Dict[str, Any]:
    pages = ((load_config(project).get("sources") or {}).get("official") or {}).get("pages", [])
    state = load_state(project)
    changes, errors, baseline = [], {}, []
    for page in pages:
        try:
            text = page_text(fetch(page["url"]))
        except RadarUnavailableError as exc:
            errors[page["id"]] = str(exc)
            continue
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        previous = state["official"].get(page["id"])
        if previous is None:
            baseline.append(page["id"])
        elif previous.get("hash") != digest:
            old_lines = set((previous.get("lines") or []))
            new_lines = [line for line in text.splitlines() if line not in old_lines][:8]
            lead = add_lead(project, {
                "title": f"{page['name']} 有更新",
                "url": page["url"],
                "description": "；".join(new_lines)[:600],
                "tool": page.get("tool", ""),
            }, source="official")
            changes.append(lead)
        state["official"][page["id"]] = {"hash": digest, "lines": text.splitlines()[:400], "checked_at": now_iso()}
    write_json(state_path(project), state)
    return {"changes": changes, "baseline": baseline, "errors": errors}


# ----------------------------------------------------------------- demo cards
DEFAULT_MOCK_DATA: Dict[str, Any] = {
    "appstore_updates": [
        {"tool": "kimi", "title": "Kimi App 更新：PPT 助手支持导出 PPTX（演示）", "content": "演示数据：更新说明提到幻灯片导出。"},
    ],
    "official_releases": [
        {"vendor": "千问", "title": "千问上线视频理解功能（演示）", "content": "演示数据：多模态视频理解全量发布。", "is_release": True},
    ],
    "manual_leads": [
        {"title": "有人说豆包的会议纪要能区分说话人了（演示）", "content": "演示数据：会议录音、纪要。"},
    ],
}


class RadarScanner:
    """Demo-only scanner kept for the dashboard's “演示” button and --mock."""

    def __init__(self, config_path: Union[str, Path] = DEFAULT_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.config = load_json(self.config_path, {}) or {}
        self.output_dir = Path(self.config.get("action_output_dir", "logs/radar_actions"))

    def get_configured_sources(self) -> Dict[str, Any]:
        return {name: {**details} for name, details in (self.config.get("sources") or {}).items() if isinstance(details, dict)}

    def filter_official_releases(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        keywords = ((self.config.get("sources") or {}).get("official") or {}).get("release_keywords", ["发布", "上线", "升级", "全量", "release", "launch"])
        kept = []
        for item in items:
            if item.get("is_release") is False:
                continue
            text = f"{item.get('title', '')} {item.get('content', '')}".lower()
            if item.get("is_release") is True or any(word.lower() in text for word in keywords):
                kept.append(item)
        return kept

    def create_action_card(self, layer: str, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        card = match_topic_and_generate_card(raw_event)
        card.update({
            "layer": layer,
            "priority": {"appstore": "📱 App 更新线索（待核实）", "official": "📢 官方类线索（待核实）"}.get(layer, "✍️ 手动线索（待核实）"),
            "mode": raw_event.get("mode", "candidate"),
            "verification": "unverified",
            "source_url": raw_event.get("url"),
            "observed_at": raw_event.get("observed_at"),
            "available_to_account": None,
            "recommended_titles": [],
            "card_type": "candidate_signal" if card["topic_id"] == "unmatched" else "test_work_order",
        })
        return card

    def format_action_card_markdown(self, card: Dict[str, Any], layer: str, event_id: str, date_str: str) -> str:
        raw = card.get("raw_event", {})
        mode_note = "演示数据，未接入真实采集，不能作为发布事实" if card.get("mode") == "demo" else "待核实候选线索"
        tools = "、".join(card.get("comparison_group", []))
        task = f"调用 `{card['prompt_file']}`（仍需人工核对任务是否适用）" if card.get("prompt_file") else "待人工确定测试任务；不能直接发布"
        return f"""## [线索工单] {date_str} | {event_id}
- **状态**：{mode_note}
- **来源**：{raw.get('source', layer)}：`{raw.get('title', '')}`
- **原始链接**：{card.get('source_url') or '未提供，需人工核对原始链接'}
- **当前账号可用性**：未验证
- **线索类别**：{card.get('priority')}
- **挂载话题**：#{card['topic_id']} {card['topic_name']}
- **标题**：待真实测试后依据结果撰写
- **测试任务包**：{task}
- **对照组**：{tools or '待定'}
"""

    def scan(self, mock_data: Optional[Dict[str, Any]] = None, output_dir: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        if mock_data is None:
            raise RadarUnavailableError("演示扫描需要显式传入演示数据；真实线索请用 --appstore-check / --official-check 或手动录入")
        if not isinstance(mock_data, dict):
            raise ValueError("mock_data must be an object")
        out = Path(output_dir) if output_dir else self.output_dir / "demo"
        out.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        events = []
        for item in mock_data.get("appstore_updates", []):
            events.append(("appstore", {"source": f"appstore_{item.get('tool', 'app')}", "title": item.get("title", ""), "category": "app_update", "description": item.get("content", ""), "mode": "demo"}))
        for item in self.filter_official_releases(mock_data.get("official_releases", [])):
            events.append(("official", {"source": f"official_{item.get('vendor', 'vendor')}", "title": item.get("title", ""), "category": "official_release", "description": item.get("content", ""), "mode": "demo"}))
        for item in mock_data.get("manual_leads", []):
            events.append(("manual", {"source": "manual", "title": item.get("title", ""), "category": "manual", "description": item.get("content", ""), "mode": "demo"}))
        cards = []
        for index, (layer, event) in enumerate(events, 1):
            card = self.create_action_card(layer, event)
            if card["card_type"] == "test_work_order":
                event_id = f"DEMO-{layer.upper()}-{index:02d}"
                path = out / f"{date_str}-{event_id.lower()}-card.md"
                write_text(path, self.format_action_card_markdown(card, layer, event_id, date_str))
                card["saved_path"] = str(path)
            cards.append(card)
        return cards


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="新品线索：App Store 版本监测、官方更新页、演示")
    parser.add_argument("--appstore-resolve", action="store_true", help="按 tools.json 的名称查找 App Store 编号候选")
    parser.add_argument("--appstore-check", action="store_true", help="对比已确认 App 的版本号")
    parser.add_argument("--official-check", action="store_true", help="对比官方更新页")
    parser.add_argument("--scan", action="store_true", help="演示扫描（需同时加 --mock）")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args(argv)
    project = Project()
    try:
        if args.appstore_resolve:
            print(json.dumps(appstore_resolve(project), ensure_ascii=False, indent=2))
        elif args.appstore_check:
            print(json.dumps(appstore_check(project), ensure_ascii=False, indent=2))
        elif args.official_check:
            print(json.dumps(official_check(project), ensure_ascii=False, indent=2))
        elif args.scan:
            if not args.mock:
                print("真实线索请用 --appstore-check 或 --official-check；演示请加 --mock", file=sys.stderr)
                return 2
            cards = RadarScanner(project.root / "scripts" / "radar_sources.json").scan(DEFAULT_MOCK_DATA, project.root / "logs" / "radar_actions" / "demo")
            print(f"演示完成：{len(cards)} 条虚构示例，均标记为演示")
        else:
            parser.print_help()
    except RadarUnavailableError as exc:
        print(f"未完成：{exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
