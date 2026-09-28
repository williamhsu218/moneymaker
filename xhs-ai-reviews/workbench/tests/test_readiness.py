"""The publication gate fails closed until evidence, review and fresh images agree."""
import pytest

from conftest import FAKE_JPEG, complete_post, fake_export
from scripts import render_carousel
from scripts.evidence_intake import save_text, set_metadata, store_bytes
from scripts.new_post import create_post
from scripts.project import load_json, write_json
from scripts.radar_dashboard import assess_post_01_readiness
from scripts.readiness import assess_post_readiness, review_post, verified_post_count


@pytest.fixture
def post(project, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    return create_post(project, "01")


def codes(readiness):
    return {item["code"] for item in readiness["blockers"]}


def test_fresh_post_is_blocked_on_every_front(project, post):
    readiness = assess_post_readiness(project, post)
    assert readiness["publishable"] is False and readiness["content_verified"] is False
    assert {"scoring_incomplete", "evidence_incomplete", "copy_blocked", "scorecard_draft"} <= codes(readiness)
    assert readiness["evidence_count"] == 0 and readiness["required_evidence_count"] == 20


def test_review_is_refused_while_content_is_incomplete(project, post):
    before = (project.post_dir(post) / "scorecard.json").read_text(encoding="utf-8")
    result = review_post(project, post, "reviewer")
    assert result["status"] == "blocked"
    assert (project.post_dir(post) / "scorecard.json").read_text(encoding="utf-8") == before


def test_complete_review_render_then_any_change_closes_the_gate(project, post):
    complete_post(project, post)
    pre = assess_post_readiness(project, post, for_review=True)
    assert pre["content_ready_for_review"] is True, pre["blockers"]
    result = review_post(project, post, "William")
    assert result["status"] == "reviewed"
    assert len(result["locked_files"]) == 20 + 5 + 1  # evidence + scorecard/copy/cards/highlights/post + metadata digest
    readiness = result["readiness"]
    assert readiness["content_verified"] is True and readiness["publishable"] is False
    assert codes(readiness) == {"assets_stale"}
    scorecard = load_json(project.post_dir(post) / "scorecard.json")
    assert scorecard["status"] == "verified" and scorecard["evaluation_date"] == "2026-09-28"

    render = render_carousel.render_post(project, post)
    assert render["draft"] is False
    assert assess_post_readiness(project, post)["publishable"] is True

    save_text(project, post, "deepseek", "prompt_a_text", "复核后又改过的回答原文，放行必须失效。")
    stale = assess_post_readiness(project, post)
    assert stale["publishable"] is False
    assert "review_stale" in codes(stale)
    assert "posts/post-01-weekly-report/evidence/deepseek/prompt-a.txt" in stale["changed_since_review"]


def test_metadata_change_after_review_is_detected(project, post):
    complete_post(project, post)
    review_post(project, post, "William")
    set_metadata(project, post, "kimi", {"version": "2.0"})
    assert "review_stale" in codes(assess_post_readiness(project, post))


def test_copy_placeholder_blocks_and_draft_images_are_labeled(project, post):
    complete_post(project, post)
    copy_path = project.post_dir(post) / "copy.md"
    copy_path.write_text(copy_path.read_text(encoding="utf-8").replace("## 笔记正文\n", "## 笔记正文\n【还没填的结论】\n"), encoding="utf-8")
    readiness = assess_post_readiness(project, post, for_review=True)
    assert "copy_blocked" in codes(readiness)
    render = render_carousel.render_post(project, post)
    assert render["draft"] is True
    html = (project.post_dir(post) / "images" / render["files"][0]["html"]).read_text(encoding="utf-8")
    assert "草稿 · 待实测，不可发布" in html


def test_jpeg_accepted_and_wrong_folder_rejected(project, post):
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "a.jpg", FAKE_JPEG)
    manifest = load_json(project.post_dir(post) / "evidence/manifest.json")
    assert manifest["tools"]["deepseek"]["files"]["prompt_a_screenshot"].endswith("prompt-a.jpg")
    manifest["tools"]["kimi"]["files"]["prompt_a_screenshot"] = manifest["tools"]["deepseek"]["files"]["prompt_a_screenshot"]
    write_json(project.post_dir(post) / "evidence/manifest.json", manifest)
    status = assess_post_readiness(project, post)
    problems = next(item for item in status["blockers"] if item["code"] == "evidence_incomplete")["details"]
    assert any("Kimi" in line and "证据文件夹" in line for line in problems)


def test_contradicting_note_is_flagged(project, post):
    complete_post(project, post)
    scorecard = load_json(project.post_dir(post) / "scorecard.json")
    scorecard["tool_results"]["deepseek"]["notes"]["trap_1"] = "踩坑：写了点击率提升20%"
    write_json(project.post_dir(post) / "scorecard.json", scorecard)
    readiness = assess_post_readiness(project, post, for_review=True)
    details = next(item for item in readiness["blockers"] if item["code"] == "scoring_incomplete")["details"]
    assert any("矛盾" in line for line in details)


def test_recap_needs_ten_verified_posts(project, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    recap = create_post(project, "12")
    complete_post(project, recap)
    assert "not_enough_posts" in codes(assess_post_readiness(project, recap, for_review=True))


def test_stale_review_does_not_count_toward_recap(project, post):
    complete_post(project, post)
    review_post(project, post, "William")
    assert verified_post_count(project) == 1
    save_text(project, post, "deepseek", "prompt_a_text", "复核后修改的回答，不能算已复核篇目。")
    assert verified_post_count(project) == 0


def test_legacy_post_01_wrapper(project, post):
    assert assess_post_01_readiness(project.root)["post_id"] == "post-01-weekly-report"
