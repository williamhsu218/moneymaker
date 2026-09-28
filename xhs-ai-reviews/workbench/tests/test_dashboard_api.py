"""HTTP API: the full post workflow, image gating and local-only security."""
import base64
import re

import pytest

from conftest import fake_export, make_png
from scripts import render_carousel
from scripts.new_post import create_post
from scripts.ops import ensure_ops_files
from scripts.radar_dashboard import RadarDashboardServer

POST = "post-01-weekly-report"


@pytest.fixture
def server(project, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    ensure_ops_files(project)
    srv = RadarDashboardServer(port=0, project_root=project.root).start()
    yield srv
    srv.stop()


@pytest.fixture
def client(server):
    return server.get_test_client()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_status_config_and_index_have_no_external_dependencies(client, project):
    assert client.get("/api/status").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert config["brand"]["account_name"] == "科技试吃员" and len(config["topics"]) == 12
    index = client.get("/")
    assert index.status_code == 200 and "科技试吃员" in index.text
    assert "http://" not in index.text and "https://" not in index.text
    for path in ("/js/app.js", "/js/logic.js", "/css/app.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert "cdn." not in response.text and "unpkg" not in response.text


def test_create_post_links_calendar(client, project):
    response = client.post("/api/posts", json={"topic_id": "5"})
    assert response.status_code == 201
    post_id = response.json()["post_id"]
    assert post_id == "post-05-excel-formula"
    slot = response.json()["detail"]["slot"]
    assert slot and slot["topic_id"] == "05"
    assert client.post("/api/posts", json={"topic_id": "05"}).status_code == 400
    listed = client.get("/api/posts").json()["posts"]
    assert [item["post_id"] for item in listed] == [post_id]


def test_full_workflow_through_the_api(client, project):
    client.post("/api/posts", json={"topic_id": "01"})
    detail = client.get(f"/api/posts/{POST}").json()
    assert detail["readiness"]["publishable"] is False
    assert client.get(f"/api/posts/{POST}/package").status_code == 409

    for tool in detail["post"]["tools"]:
        r = client.post(f"/api/posts/{POST}/evidence/meta", json={"tool": tool, "fields": {"model": "m", "version": "1", "platform": "iOS", "settings": "默认", "free_tier": "免费", "tested_at": "2026-09-28T20:30:00+08:00"}})
        assert r.status_code == 200, r.text
        for key in ("prompt_a_text", "prompt_b_text"):
            assert client.post(f"/api/posts/{POST}/evidence/text", json={"scope": tool, "key": key, "text": "合成测试回答原文，仅用于自动化测试。"}).status_code == 200
        for key in ("prompt_a_screenshot", "prompt_b_screenshot"):
            assert client.post(f"/api/posts/{POST}/evidence/file", json={"scope": tool, "key": key, "filename": "s.png", "data_base64": b64(make_png())}).status_code == 200
    image = client.get(f"/api/posts/{POST}/evidence-file?scope=kimi&key=prompt_a_screenshot")
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")

    checks = detail["scorecard"]["checks"]
    results = {tool: {"checks": {key: "pass" for key in checks}, "notes": {key: "原文如实" for key in checks}, "total_score": 4, "verdict": "能交", "summary": "合成结论", "gut_reaction": "合成感受"} for tool in detail["post"]["tools"]}
    assert client.post(f"/api/posts/{POST}/scorecard", json={"tool_results": results}).status_code == 200
    blocked = client.post(f"/api/posts/{POST}/review", json={"reviewed_by": "W", "confirm": True})
    assert blocked.status_code == 409 and blocked.json()["status"] == "blocked"

    copy = client.get(f"/api/posts/{POST}").json()["copy"]
    filled = re.sub(r"【[^】]*】", "合成", copy)
    assert client.post(f"/api/posts/{POST}/copy", json={"text": filled}).status_code == 200
    assert client.post(f"/api/posts/{POST}/review", json={"reviewed_by": "W"}).status_code == 400
    reviewed = client.post(f"/api/posts/{POST}/review", json={"reviewed_by": "W", "confirm": True})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["readiness"]["content_verified"] is True

    rendered = client.post(f"/api/posts/{POST}/render", json={})
    assert rendered.status_code == 200 and rendered.json()["draft"] is False
    files = rendered.json()["detail"]["images"]["files"]
    first = files[0]["url"]
    assert client.get(first).status_code == 200
    package = client.get(f"/api/posts/{POST}/package")
    assert package.status_code == 200 and package.json()["title"]
    assert client.post(f"/api/posts/{POST}/published", json={"published_at": "2026-09-28T20:40:00+08:00"}).status_code == 200

    # Any claim change after review: final images stop being served, package closes.
    client.post(f"/api/posts/{POST}/evidence/text", json={"scope": "kimi", "key": "prompt_a_text", "text": "改过的回答原文，复核必须失效。"})
    assert client.get(first).status_code == 409
    assert client.get(f"/api/posts/{POST}/package").status_code == 409
    assert "review_stale" in {item["code"] for item in client.get(f"/api/posts/{POST}").json()["readiness"]["blockers"]}


def test_draft_images_are_served_and_unlisted_files_are_not(client, project):
    create_post(project, "01")
    rendered = client.post(f"/api/posts/{POST}/render", json={})
    assert rendered.json()["draft"] is True
    url = rendered.json()["detail"]["images"]["files"][0]["url"]
    assert client.get(url).status_code == 200
    (project.post_dir(POST) / "images" / "old.png").write_bytes(make_png())
    assert client.get(f"/assets/posts/{POST}/images/old.png").status_code == 403
    assert client.get(f"/assets/posts/{POST}/evidence/manifest.json").status_code == 403
    assert client.get(f"/assets/posts/{POST}/scorecard.json").status_code == 403


def test_settings_highlights_and_cards_validation(client, project):
    create_post(project, "03")
    post = "post-03-primary-math"
    bad = client.post(f"/api/posts/{post}/settings", json={"cover": {"tag": "家长必看", "lines": ["这一行标题实在是太长了超过了十六个字限制"], "palette": "yellow"}})
    assert bad.status_code == 400
    ok = client.post(f"/api/posts/{post}/settings", json={"cover": {"tag": "家长必看", "lines": ["孩子的数学题", "谁讲得明白？"], "palette": "mint"}, "picks": {"2": ["kimi", "doubao"]}})
    assert ok.status_code == 200 and ok.json()["post"]["cover"]["palette"] == "mint"
    assert client.post(f"/api/posts/{post}/highlights", json={"tool": "kimi", "key": "q1_screenshot", "boxes": [{"x": 2, "y": 0, "w": 0.1, "h": 0.1}]}).status_code == 400
    good = client.post(f"/api/posts/{post}/highlights", json={"tool": "kimi", "key": "q1_screenshot", "boxes": [{"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.1, "note": "用了方程"}], "crop": {"y0": 0, "y1": 0.6}})
    assert good.status_code == 200 and good.json()["highlights"]["kimi"]["q1_screenshot"]["boxes"][0]["note"] == "用了方程"
    assert client.post(f"/api/posts/{post}/highlights", json={"tool": "kimi", "key": "q1_screenshot", "masks": [{"x": 0.8, "y": 0.1, "w": 0.3, "h": 0.1}]}).status_code == 400
    masked = client.post(f"/api/posts/{post}/highlights", json={"tool": "kimi", "key": "q1_screenshot", "masks": [{"x": 0.03, "y": 0.02, "w": 0.25, "h": 0.07}]})
    saved = masked.json()["highlights"]["kimi"]["q1_screenshot"]
    assert masked.status_code == 200 and saved["masks"][0]["w"] == 0.25
    assert saved["boxes"][0]["note"] == "用了方程"  # Updating masks does not erase red boxes.
    tools = client.post(f"/api/posts/{post}/settings", json={"tools": ["kimi", "doubao", "deepseek"]})
    assert tools.status_code == 200 and tools.json()["scorecard"]["tools"] == ["kimi", "doubao", "deepseek"]
    assert client.post(f"/api/posts/{post}/settings", json={"tools": ["kimi"]}).status_code == 400


def test_ops_endpoints(client, project):
    create_post(project, "01")
    assert client.get("/api/calendar").json()["weeks"][0]["slots"][0]["display_status"] == "备题"
    assert client.post("/api/metrics", json={"row": {"post_id": POST, "checkpoint": "24h", "views": "100"}}).status_code == 200
    assert client.post("/api/requests", json={"request": "测AI写文案"}).json()["rows"][0]["count"] == "1"
    review = client.post("/api/reviews/weekly", json={"week": 1})
    assert review.status_code == 200 and review.json()["path"] == "ops/reviews/week-1.md"
    account = client.get("/api/account").json()
    account["audit"]["nickname"] = "原昵称"
    assert client.post("/api/account", json=account).json()["audit"]["nickname"] == "原昵称"
    assert client.post("/api/leads", json={"title": "新功能", "url": "https://example.com/a"}).status_code == 200
    assert client.post("/api/leads/L0001", json={"status": "忽略"}).json()["rows"][0]["status"] == "忽略"
    assert client.post("/api/radar/scan", json={"mock": False}).status_code == 501
    demo = client.post("/api/radar/scan", json={"mock": True}).json()
    assert demo["mode"] == "demo" and demo["count"] > 0
    assert client.get("/api/radar/cards").json()["count"] > 0


def test_calendar_editor_cannot_create_or_erase_publication(client, project):
    created = client.post("/api/posts", json={"topic_id": "01"})
    assert created.status_code == 201
    calendar = client.get("/api/calendar").json()
    slot = calendar["weeks"][0]["slots"][0]
    assert slot["post_id"] == POST
    assert client.post(f"/api/posts/{POST}/published", json={"published_at": "2026-09-28T20:40:00+08:00"}).status_code == 400

    slot["status"] = "已发布"
    slot["published_at"] = "2026-09-28T20:40:00+08:00"
    assert client.post("/api/calendar", json={"calendar": calendar}).status_code == 400
    assert client.get("/api/calendar").json()["weeks"][0]["slots"][0]["status"] == "备题"

    slot["status"] = "备题"
    assert client.post("/api/calendar", json={"calendar": calendar}).status_code == 400

    # An already recorded publication survives ordinary schedule edits.
    from scripts import ops
    ops.mark_published(project, POST, "2026-09-28T20:40:00+08:00")
    calendar = client.get("/api/calendar").json()
    calendar["weeks"][0]["slots"][1]["note"] = "本周调整测试安排"
    assert client.post("/api/calendar", json={"calendar": calendar}).status_code == 200

    calendar = client.get("/api/calendar").json()
    calendar["weeks"][0]["slots"][0]["status"] = "备题"
    assert client.post("/api/calendar", json={"calendar": calendar}).status_code == 400
    calendar["weeks"][0]["slots"][0]["status"] = "已发布"
    calendar["weeks"][0]["slots"][0]["published_at"] = "2026-09-28T21:00:00+08:00"
    assert client.post("/api/calendar", json={"calendar": calendar}).status_code == 400
    calendar["weeks"][0]["slots"][0]["published_at"] = "2026-09-28T20:40:00+08:00"
    calendar["weeks"][0]["slots"][0]["date"] = "2026-09-29"
    assert client.post("/api/calendar", json={"calendar": calendar}).status_code == 400
    saved = client.get("/api/calendar").json()["weeks"][0]["slots"][0]
    assert saved["status"] == "已发布" and saved["published_at"] == "2026-09-28T20:40:00+08:00"


def test_cross_origin_writes_and_traversal_are_blocked(client, server, project):
    create_post(project, "01")
    trusted = f"http://127.0.0.1:{server.port}"
    assert client.options("/api/status", headers={"Origin": trusted}).status_code == 204
    assert client.options("/api/status", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/posts", json={"topic_id": "02"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/posts", json={"topic_id": "02"}, headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get("/assets/../../etc/passwd").status_code in (403, 404)
    assert client.get("/assets/scripts/radar_dashboard.py").status_code == 403
    assert client.get(f"/api/posts/{POST}/inbox-file?name=../post.json").status_code == 400
    leak = project.root / "web" / "js" / "leak.js"
    leak.symlink_to(project.post_dir(POST) / "evidence" / "manifest.json")
    assert client.get("/js/leak.js").status_code == 403
    assert client.get("/api/posts/post-99-nope").status_code == 404
    assert client.get("/api/nothing").status_code == 404


def test_legacy_post_01_route(client, project):
    create_post(project, "01")
    data = client.get("/api/post/01").json()
    assert data["post_id"] == POST and "scorecard" in data and "copy" in data
