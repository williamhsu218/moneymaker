"""Calendar, metrics, account audit, requests, leads, weekly review and handoff."""
from datetime import date

import pytest

from conftest import complete_post
from scripts import ops
from scripts.handoff import handoff_markdown
from scripts.new_post import create_post
from scripts.project import ProjectError, load_json
from scripts.weekly_review import review_markdown


def test_default_calendar_has_four_weeks_of_three_plus_one(project):
    calendar = ops.default_calendar(project, start=date(2026, 9, 28))
    assert calendar["start_date"] == "2026-09-28"
    assert len(calendar["weeks"]) == 4
    for week in calendar["weeks"]:
        kinds = [slot["kind"] for slot in week["slots"]]
        assert kinds == ["fixed", "fixed", "fixed", "flex"]
    assert [slot["topic_id"] for slot in calendar["weeks"][0]["slots"][:3]] == ["01", "05", "02"]
    assert calendar["weeks"][0]["slots"][1]["date"] == "2026-09-30"


def test_calendar_validation_and_linking(project):
    ops.ensure_ops_files(project)
    post = create_post(project, "05")
    ops.attach_post(project, "05", post)
    calendar = ops.load_calendar(project)
    assert calendar["weeks"][0]["slots"][1]["post_id"] == post
    calendar["weeks"][0]["slots"][0]["topic_id"] = "99"
    with pytest.raises(ProjectError):
        ops.save_calendar(project, calendar)
    with pytest.raises(ProjectError):
        ops.mark_published(project, post, "昨晚")
    slot = ops.mark_published(project, post, "2026-09-30T20:30:00+08:00")
    assert slot["status"] == "已发布"


def test_first_post_before_first_launch_is_linked_once(project):
    post = create_post(project, "01")
    ops.attach_post(project, "01", post)
    ops.ensure_ops_files(project)
    slots = [slot for week in ops.load_calendar(project)["weeks"] for slot in week["slots"]]
    assert sum(slot.get("post_id") == post for slot in slots) == 1
    assert slots[3]["kind"] == "flex" and slots[3]["post_id"] is None


def test_derived_status():
    assert ops.derived_status(None, {"status": "备题"}) == "备题"
    assert ops.derived_status({"publishable": True}, {"status": "备题"}) == "可发布"
    assert ops.derived_status({"publishable": False, "content_ready_for_review": True}, {}) == "待复核"
    assert ops.derived_status({"publishable": False, "evidence_count": 3}, {}) == "测试中"
    assert ops.derived_status({"publishable": True}, {"status": "已发布"}) == "已发布"


def test_metrics_upsert_and_validation(project):
    post = create_post(project, "01")
    ops.upsert_metric(project, {"post_id": post, "checkpoint": "24h", "views": "1000", "saves": "80"})
    ops.upsert_metric(project, {"post_id": post, "checkpoint": "24h", "views": "1200", "saves": "90"})
    rows = ops.load_metrics(project)
    assert len(rows) == 1 and rows[0]["views"] == "1200" and rows[0]["format"] == "cmp"
    with pytest.raises(ProjectError):
        ops.upsert_metric(project, {"post_id": post, "checkpoint": "1h"})
    with pytest.raises(ProjectError):
        ops.upsert_metric(project, {"post_id": post, "checkpoint": "72h", "views": "-1"})


def test_account_checklist_dates_and_followers(project):
    data = ops.load_account(project)
    assert data["checklist"][0]["id"] == "audit"
    data["checklist"][0]["done"] = True
    data["audit"]["nickname"] = "原昵称"
    data["followers"] = [{"date": "2026-09-28", "count": 120}]
    saved = ops.save_account(project, data)
    assert saved["checklist"][0]["date"] == date.today().isoformat()
    assert load_json(project.ops_dir / "account_audit.json")["audit"]["nickname"] == "原昵称"
    with pytest.raises(ProjectError):
        ops.save_account(project, {"audit": {"old_posts_decision": "delete_all"}})


def test_requests_accumulate(project):
    ops.add_request(project, {"request": "测AI写小红书文案"})
    ops.add_request(project, {"request": "测AI写小红书文案", "count": 2})
    ops.add_request(project, {"request": "测AI做海报"})
    top = ops.top_requests(project)
    assert top[0]["request"] == "测AI写小红书文案" and top[0]["count"] == "3"
    ops.update_request(project, "测AI写小红书文案", "已排期")
    with pytest.raises(ProjectError):
        ops.update_request(project, "测AI做海报", "随便")


def test_leads_validation_and_dedupe(project):
    first = ops.add_lead(project, {"title": "千问上线视频理解", "url": "https://www.qianwen.com", "tool": "qianwen"})
    again = ops.add_lead(project, {"title": "千问上线视频理解", "url": "https://www.qianwen.com"})
    assert first["id"] == again["id"] == "L0001" and first["status"] == "待核实"
    with pytest.raises(ProjectError):
        ops.add_lead(project, {"title": "x", "url": "javascript:alert(1)"})
    updated = ops.update_lead(project, "L0001", {"available_in_my_app": "是", "status": "已核实可测"})
    assert updated["status"] == "已核实可测"


def test_weekly_review_ratios_and_small_sample_note(project):
    ops.ensure_ops_files(project)
    a = create_post(project, "01")
    b = create_post(project, "05")
    ops.upsert_metric(project, {"post_id": a, "checkpoint": "24h", "published_at": "2026-09-28T20:30:00+08:00", "views": "1000", "saves": "50", "new_followers": "10"})
    ops.upsert_metric(project, {"post_id": a, "checkpoint": "72h", "published_at": "2026-09-28T20:30:00+08:00", "views": "2000", "saves": "200", "new_followers": "40"})
    ops.upsert_metric(project, {"post_id": b, "checkpoint": "24h", "published_at": "2026-09-30T20:30:00+08:00", "views": "500", "saves": "10", "new_followers": "1"})
    ops.add_request(project, {"request": "测AI写小红书文案"})
    text = review_markdown(project, 1)
    assert "| post-01-weekly-report | 横评 | 72h | 2000" in text
    assert "10.0%" in text and "样本不足" in text
    assert "测AI写小红书文案" in text
    assert "下月配比" in review_markdown(project, 4)


def test_handoff_contains_results_and_voice(project):
    post = create_post(project, "01")
    complete_post(project, post)
    text = handoff_markdown(project, post)
    assert "我是科技试吃员" in text and "评论区点菜" in text
    for name in ("DeepSeek", "豆包", "Kimi", "腾讯元宝", "千问"):
        assert f"### {name}" in text
    assert "第一反应（原话）：还行" in text
    assert "evidence/deepseek/prompt-a.txt" in text
    assert "不要改 scorecard.json 和 evidence/" in text
