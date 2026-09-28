"""File-backed operations data: calendar, metrics, account audit, comment
requests and benchmark notes. Everything lives under ops/ so it survives
browser changes and Claude can read it directly.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
import io
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

try:
    from scripts.project import Project, ProjectError, load_json, now_iso, valid_date, valid_datetime, write_json, write_text
except ImportError:  # pragma: no cover
    from project import Project, ProjectError, load_json, now_iso, valid_date, valid_datetime, write_json, write_text  # type: ignore

SLOT_STATUSES = ["备题", "测试中", "待复核", "可发布", "已发布", "跳过"]
METRIC_FIELDS = ["post_id", "format", "published_at", "checkpoint", "views", "likes", "saves", "comments", "shares", "new_followers", "production_minutes", "notes"]
METRIC_NUMBERS = ["views", "likes", "saves", "comments", "shares", "new_followers", "production_minutes"]
CHECKPOINTS = ["24h", "72h", "7d"]
REQUEST_FIELDS = ["date", "post_id", "request", "count", "status"]
REQUEST_STATUSES = ["新", "已排期", "已做", "不做"]
BENCHMARK_FIELDS = ["added", "title", "author", "url_note", "cover_structure", "image_count", "saves", "likes", "takeaway", "screenshot"]
LEAD_FIELDS = ["id", "found_at", "source", "title", "url", "description", "tool", "available_in_my_app", "status", "topic_id", "note"]
LEAD_STATUSES = ["待核实", "已核实可测", "暂不可测", "已建篇", "忽略"]

DEFAULT_CHECKLIST = [
    {"id": "audit", "label": "盘点现有账号：主页、最近 10 篇数据、粉丝互动"},
    {"id": "realname", "label": "按 App 当前提示核对实名认证及商业合作资格"},
    {"id": "name", "label": "改昵称（建议“科技试吃员”或“原昵称｜科技试吃员”）"},
    {"id": "bio", "label": "改简介（三行，见 brand.json）"},
    {"id": "avatar", "label": "换头像：清晰本人照或黄/墨绿简洁图标，不放二维码和联系方式"},
    {"id": "hide_posts", "label": "逐篇判断不相关的旧帖；需要时设为仅自己可见，并保留原记录"},
    {"id": "feed", "label": "浏览 AI 测评/工具类内容，记录受众问题和可借鉴的表达"},
    {"id": "benchmarks", "label": "收藏 10 篇高收藏的 AI 笔记，截图放进 ops/benchmarks/"},
    {"id": "collections", "label": "建 3 个合集：AI横评、AI教程、新品实测"},
    {"id": "apps", "label": "装好第 1 期的 5 个 App 并注册"},
    {"id": "pin", "label": "有 2–3 篇表现好的笔记后置顶"},
]
DEFAULT_PLAN = [["01", "05", "02"], ["07", "04", "06"], ["03", "08", "09"], ["10", "11", "12"]]


# --------------------------------------------------------------------- helpers
def _read_csv(path: Path, fields: List[str]) -> List[Dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [{field: (row.get(field) or "") for field in fields} for row in csv.DictReader(handle)]


def _write_csv(path: Path, fields: List[str], rows: List[Dict[str, Any]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})
    write_text(path, buffer.getvalue())


def _clean(value: Any, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r", " ").strip()
    if len(text) > limit:
        raise ProjectError(f"内容太长（超过 {limit} 字）")
    return text


def _next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7) if today.weekday() else today


# -------------------------------------------------------------------- calendar
def default_calendar(project: Project, start: Optional[date] = None) -> Dict[str, Any]:
    start = start or _next_monday(date.today())
    offsets = [0, 2, 4]  # Mon / Wed / Fri
    weeks = []
    for week_index, topics in enumerate(DEFAULT_PLAN):
        monday = start + timedelta(days=7 * week_index)
        slots = [
            {"date": (monday + timedelta(days=offset)).isoformat(), "kind": "fixed", "topic_id": topic_id, "post_id": None, "status": "备题", "published_at": None, "note": ""}
            for offset, topic_id in zip(offsets, topics)
        ]
        slots.append({"date": (monday + timedelta(days=5)).isoformat(), "kind": "flex", "topic_id": None, "post_id": None, "status": "备题", "published_at": None, "note": "机动位：48 小时新品，或上周表现最好题材的第二轮"})
        weeks.append({"week": week_index + 1, "slots": slots})
    weeks[3]["slots"][2]["note"] = "前提：至少 10 期完成复核；不够就换成机动选题"
    existing: Dict[str, List[str]] = {}
    for post_id in project.list_posts():
        try:
            existing.setdefault(project.load_post(post_id).get("topic_id", ""), []).append(post_id)
        except ProjectError:
            continue
    for week in weeks:
        for slot in week["slots"]:
            queue = existing.get(slot.get("topic_id") or "")
            if queue:
                slot["post_id"] = queue.pop(0)
    return {
        "start_date": start.isoformat(),
        "publish_window": project.brand().get("publish_window", "20:00–21:00（待验证）"),
        "note": "每周 3 个固定位 + 1 个机动位。日期和选题都可以改；“已发布”只能由你手动标记。",
        "weeks": weeks,
    }


def calendar_path(project: Project) -> Path:
    return project.ops_dir / "calendar.json"


def load_calendar(project: Project) -> Dict[str, Any]:
    data = load_json(calendar_path(project))
    if not isinstance(data, dict) or not isinstance(data.get("weeks"), list):
        data = default_calendar(project)
    return data


def validate_calendar(project: Project, data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict) or not isinstance(data.get("weeks"), list):
        raise ProjectError("排期格式无效")
    topic_ids = {topic["id"] for topic in project.topics()}
    if not valid_date(data.get("start_date")):
        raise ProjectError("start_date 需为 YYYY-MM-DD")
    for week in data["weeks"]:
        if not isinstance(week, dict) or not isinstance(week.get("slots"), list):
            raise ProjectError("每周需要 slots 列表")
        for slot in week["slots"]:
            if not isinstance(slot, dict) or not valid_date(slot.get("date")):
                raise ProjectError("每个坑位需要有效日期")
            if slot.get("topic_id") not in (None, "") and slot["topic_id"] not in topic_ids:
                raise ProjectError(f"未知选题 {slot['topic_id']}")
            if slot.get("post_id") not in (None, "") and not project.post_exists(slot["post_id"]):
                raise ProjectError(f"篇目不存在：{slot['post_id']}")
            if slot.get("status", "备题") not in SLOT_STATUSES:
                raise ProjectError(f"状态只能是：{'、'.join(SLOT_STATUSES)}")
            if slot.get("published_at") not in (None, "") and not valid_datetime(slot["published_at"]):
                raise ProjectError("发布时间格式无效")
            slot["note"] = _clean(slot.get("note"), 300)
    return data


def save_calendar(project: Project, data: Any) -> Dict[str, Any]:
    data = validate_calendar(project, data)
    # Publication is a recorded event, not a scheduling choice.  The calendar
    # editor may rearrange future slots, but only mark_published (after the
    # readiness gate in the API) may create or change a published record.
    def publication_records(calendar: Dict[str, Any]) -> List[tuple]:
        return sorted(
            (week_index, slot_index, str(slot.get("date") or ""), str(slot.get("kind") or ""),
             str(slot.get("topic_id") or ""), str(slot.get("post_id") or ""),
             str(slot.get("status") or ""), str(slot.get("published_at") or ""))
            for week_index, week in enumerate(calendar.get("weeks", []))
            for slot_index, slot in enumerate(week.get("slots", []))
            if slot.get("status") == "已发布" or slot.get("published_at") not in (None, "")
        )

    if publication_records(data) != publication_records(load_calendar(project)):
        raise ProjectError("排期不能新增、取消或改动已发布记录；请在篇目发布页标记实际发布时间")
    write_json(calendar_path(project), data)
    return data


def attach_post(project: Project, topic_id: str, post_id: str) -> None:
    """Link a newly created post to the first open slot of its topic."""
    data = load_calendar(project)
    # When the calendar file does not exist yet, default_calendar already
    # discovers the new workspace. Do not attach it again to a flex slot.
    if any(slot.get("post_id") == post_id for week in data["weeks"] for slot in week["slots"]):
        return
    for week in data["weeks"]:
        for slot in week["slots"]:
            if slot.get("topic_id") == topic_id and not slot.get("post_id"):
                slot["post_id"] = post_id
                write_json(calendar_path(project), data)
                return
    for week in data["weeks"]:
        for slot in week["slots"]:
            if slot.get("kind") == "flex" and not slot.get("post_id") and not slot.get("topic_id"):
                slot["topic_id"] = topic_id
                slot["post_id"] = post_id
                write_json(calendar_path(project), data)
                return


def derived_status(readiness: Optional[Dict[str, Any]], slot: Dict[str, Any]) -> str:
    """Status shown on the board: manual 已发布/跳过 wins, otherwise from the gate."""
    if slot.get("status") in ("已发布", "跳过"):
        return slot["status"]
    if not readiness:
        return "备题"
    if readiness.get("publishable"):
        return "可发布"
    if readiness.get("content_ready_for_review") or readiness.get("content_verified"):
        return "待复核"
    if readiness.get("evidence_count", 0) > 0:
        return "测试中"
    return "备题"


def mark_published(project: Project, post_id: str, published_at: str) -> Dict[str, Any]:
    if not valid_datetime(published_at):
        raise ProjectError("发布时间格式无效")
    data = load_calendar(project)
    for week in data["weeks"]:
        for slot in week["slots"]:
            if slot.get("post_id") == post_id:
                slot["status"] = "已发布"
                slot["published_at"] = published_at
                write_json(calendar_path(project), data)
                return slot
    raise ProjectError("排期里没有这一篇，先把它放进一个坑位")


def week_of(project: Project, when: str) -> Optional[int]:
    data = load_calendar(project)
    try:
        start = date.fromisoformat(data["start_date"])
        day = datetime.fromisoformat(when.replace("Z", "+00:00")).date() if "T" in when else date.fromisoformat(when[:10])
    except (KeyError, ValueError):
        return None
    delta = (day - start).days
    return delta // 7 + 1 if delta >= 0 else None


# --------------------------------------------------------------------- metrics
def metrics_path(project: Project) -> Path:
    return project.ops_dir / "metrics.csv"


def load_metrics(project: Project) -> List[Dict[str, str]]:
    return _read_csv(metrics_path(project), METRIC_FIELDS)


def upsert_metric(project: Project, row: Dict[str, Any]) -> Dict[str, str]:
    post_id = project.check_post_id(str(row.get("post_id", "")))
    if not project.post_exists(post_id):
        raise ProjectError("篇目不存在")
    checkpoint = row.get("checkpoint")
    if checkpoint not in CHECKPOINTS:
        raise ProjectError(f"checkpoint 只能是 {'/'.join(CHECKPOINTS)}")
    clean: Dict[str, str] = {"post_id": post_id, "checkpoint": checkpoint}
    topic = project.post_topic(post_id)
    clean["format"] = topic.get("format", "")
    published = _clean(row.get("published_at"), 40)
    if published and not valid_datetime(published):
        raise ProjectError("发布时间格式无效")
    clean["published_at"] = published
    for field in METRIC_NUMBERS:
        value = row.get(field)
        if value in (None, ""):
            clean[field] = ""
            continue
        try:
            number = int(float(value))
        except (TypeError, ValueError) as exc:
            raise ProjectError(f"{field} 需为数字") from exc
        if number < 0:
            raise ProjectError(f"{field} 不能是负数")
        clean[field] = str(number)
    clean["notes"] = _clean(row.get("notes"), 500)
    rows = [item for item in load_metrics(project) if not (item["post_id"] == post_id and item["checkpoint"] == checkpoint)]
    rows.append(clean)
    rows.sort(key=lambda item: (item["post_id"], CHECKPOINTS.index(item["checkpoint"]) if item["checkpoint"] in CHECKPOINTS else 9))
    _write_csv(metrics_path(project), METRIC_FIELDS, rows)
    return clean


# --------------------------------------------------------------------- account
def account_path(project: Project) -> Path:
    return project.ops_dir / "account_audit.json"


def load_account(project: Project) -> Dict[str, Any]:
    data = load_json(account_path(project))
    if not isinstance(data, dict):
        data = {}
    data.setdefault("audit", {"nickname": "", "follower_count": "", "bio": "", "audience": "", "recent_ten": "", "old_posts_decision": "undecided", "decision_reason": ""})
    existing = {item.get("id"): item for item in data.get("checklist", []) if isinstance(item, dict)}
    data["checklist"] = [{**item, "done": bool(existing.get(item["id"], {}).get("done")), "date": existing.get(item["id"], {}).get("date", ""), "note": existing.get(item["id"], {}).get("note", "")} for item in DEFAULT_CHECKLIST]
    data.setdefault("followers", [])
    return data


def save_account(project: Project, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProjectError("账号盘点格式无效")
    data = load_account(project)
    audit = payload.get("audit") or {}
    for key in data["audit"]:
        if key in audit:
            data["audit"][key] = _clean(audit[key], 4000 if key == "recent_ten" else 500)
    if data["audit"]["old_posts_decision"] not in ("undecided", "keep", "review"):
        raise ProjectError("旧帖处理决定无效")
    marks = {item.get("id"): item for item in payload.get("checklist", []) if isinstance(item, dict)}
    for item in data["checklist"]:
        mark = marks.get(item["id"])
        if mark is None:
            continue
        done = bool(mark.get("done"))
        if done and not item["done"]:
            item["date"] = date.today().isoformat()
        if not done:
            item["date"] = ""
        item["done"] = done
        item["note"] = _clean(mark.get("note"), 300)
    followers = payload.get("followers")
    if isinstance(followers, list):
        clean_followers = []
        for point in followers:
            if not isinstance(point, dict) or not valid_date(point.get("date")):
                raise ProjectError("粉丝记录需要日期")
            try:
                count = int(point.get("count"))
            except (TypeError, ValueError) as exc:
                raise ProjectError("粉丝数需为整数") from exc
            clean_followers.append({"date": point["date"], "count": count})
        data["followers"] = sorted(clean_followers, key=lambda point: point["date"])
    data["updated_at"] = now_iso()
    write_json(account_path(project), data)
    return data


# -------------------------------------------------------------------- requests
def requests_path(project: Project) -> Path:
    return project.ops_dir / "requests.csv"


def load_requests(project: Project) -> List[Dict[str, str]]:
    return _read_csv(requests_path(project), REQUEST_FIELDS)


def add_request(project: Project, payload: Dict[str, Any]) -> Dict[str, str]:
    request = _clean(payload.get("request"), 200)
    if not request:
        raise ProjectError("请写下评论里点的菜")
    post_id = _clean(payload.get("post_id"), 80)
    if post_id:
        project.check_post_id(post_id)
    rows = load_requests(project)
    for row in rows:
        if row["request"] == request:
            row["count"] = str(int(row.get("count") or 1) + max(1, int(payload.get("count") or 1)))
            _write_csv(requests_path(project), REQUEST_FIELDS, rows)
            return row
    row = {"date": date.today().isoformat(), "post_id": post_id, "request": request, "count": str(max(1, int(payload.get("count") or 1))), "status": "新"}
    rows.append(row)
    _write_csv(requests_path(project), REQUEST_FIELDS, rows)
    return row


def update_request(project: Project, request: str, status: str) -> None:
    if status not in REQUEST_STATUSES:
        raise ProjectError(f"状态只能是 {'、'.join(REQUEST_STATUSES)}")
    rows = load_requests(project)
    for row in rows:
        if row["request"] == request:
            row["status"] = status
    _write_csv(requests_path(project), REQUEST_FIELDS, rows)


def top_requests(project: Project, limit: int = 3) -> List[Dict[str, str]]:
    rows = [row for row in load_requests(project) if row.get("status") in ("新", "已排期")]
    return sorted(rows, key=lambda row: -int(row.get("count") or 0))[:limit]


# ------------------------------------------------------------------ benchmarks
def benchmarks_path(project: Project) -> Path:
    return project.ops_dir / "benchmarks" / "benchmarks.csv"


def load_benchmarks(project: Project) -> List[Dict[str, str]]:
    return _read_csv(benchmarks_path(project), BENCHMARK_FIELDS)


def add_benchmark(project: Project, payload: Dict[str, Any]) -> Dict[str, str]:
    title = _clean(payload.get("title"), 120)
    if not title:
        raise ProjectError("请填写对标笔记标题")
    row = {field: _clean(payload.get(field), 300) for field in BENCHMARK_FIELDS}
    row["added"] = date.today().isoformat()
    row["title"] = title
    rows = load_benchmarks(project)
    rows.append(row)
    _write_csv(benchmarks_path(project), BENCHMARK_FIELDS, rows)
    return row


# ----------------------------------------------------------------------- leads
def leads_path(project: Project) -> Path:
    return project.ops_dir / "leads.csv"


def load_leads(project: Project) -> List[Dict[str, str]]:
    return _read_csv(leads_path(project), LEAD_FIELDS)


def add_lead(project: Project, payload: Dict[str, Any], *, source: str = "manual") -> Dict[str, str]:
    title = _clean(payload.get("title"), 200)
    if not title:
        raise ProjectError("请用一句话写下线索")
    url = _clean(payload.get("url"), 500)
    if url and not re.match(r"^https?://", url):
        raise ProjectError("链接需以 http:// 或 https:// 开头")
    tool = _clean(payload.get("tool"), 40)
    if tool and tool not in project.tool_map():
        raise ProjectError("未知工具")
    available = payload.get("available_in_my_app", "未确认")
    if available not in ("是", "否", "未确认"):
        raise ProjectError("“我的 App 里能用吗”只能是 是/否/未确认")
    rows = load_leads(project)
    key = (title, url)
    for row in rows:
        if (row["title"], row["url"]) == key:
            return row
    row = {
        "id": f"L{len(rows) + 1:04d}",
        "found_at": now_iso(),
        "source": source,
        "title": title,
        "url": url,
        "description": _clean(payload.get("description"), 800),
        "tool": tool,
        "available_in_my_app": available,
        "status": "待核实",
        "topic_id": _clean(payload.get("topic_id"), 4),
        "note": _clean(payload.get("note"), 300),
    }
    rows.append(row)
    _write_csv(leads_path(project), LEAD_FIELDS, rows)
    return row


def update_lead(project: Project, lead_id: str, payload: Dict[str, Any]) -> Dict[str, str]:
    rows = load_leads(project)
    for row in rows:
        if row["id"] == lead_id:
            if "status" in payload:
                if payload["status"] not in LEAD_STATUSES:
                    raise ProjectError(f"状态只能是 {'、'.join(LEAD_STATUSES)}")
                row["status"] = payload["status"]
            if "available_in_my_app" in payload:
                if payload["available_in_my_app"] not in ("是", "否", "未确认"):
                    raise ProjectError("可用性只能是 是/否/未确认")
                row["available_in_my_app"] = payload["available_in_my_app"]
            if "note" in payload:
                row["note"] = _clean(payload["note"], 300)
            if "topic_id" in payload:
                row["topic_id"] = _clean(payload["topic_id"], 4)
            _write_csv(leads_path(project), LEAD_FIELDS, rows)
            return row
    raise ProjectError("没有这条线索")


def ensure_ops_files(project: Project) -> None:
    """Create empty ops files with headers so the folder documents itself."""
    if not calendar_path(project).exists():
        write_json(calendar_path(project), default_calendar(project))
    for path, fields in ((metrics_path(project), METRIC_FIELDS), (requests_path(project), REQUEST_FIELDS), (leads_path(project), LEAD_FIELDS), (benchmarks_path(project), BENCHMARK_FIELDS)):
        if not path.exists():
            _write_csv(path, fields, [])
    if not account_path(project).exists():
        data = load_account(project)
        write_json(account_path(project), data)
    (project.ops_dir / "inbox").mkdir(parents=True, exist_ok=True)
