"""The full image set: draft marks, embedded screenshots, highlight boxes, PNG export."""
import base64
import pytest

from conftest import complete_post, fake_export, make_png
from scripts import cards, render_carousel
from scripts.evidence_intake import store_bytes
from scripts.generate_post_assets import export_html_to_png
from scripts.new_post import create_post
from scripts.project import Project, ProjectError, image_size, load_json, write_json


@pytest.fixture
def post(project):
    return create_post(project, "01")


def test_image_order_expands_one_frame_per_tool(project, post):
    items = render_carousel.build_items(project, post, draft=True)
    assert [item["kind"] for item in items] == ["cover", "rules"] + ["evidence_each"] * 5 + ["scorecard", "conclusion"]
    assert [item["tool"] for item in items if item["kind"] == "evidence_each"] == ["deepseek", "doubao", "kimi", "yuanbao", "qianwen"]
    assert all(cards.DRAFT_TEXT in item["html"] for item in items)
    assert "09/09" in items[-1]["html"]


def test_cover_uses_post_lines_palette_and_tool_names(project, post):
    html = render_carousel.build_items(project, post, draft=False)[0]["html"]
    assert "同一份周报" in html and "谁在瞎编？" in html
    for name in ("DeepSeek", "豆包", "Kimi", "腾讯元宝", "千问"):
        assert name in html
    assert "#f2d34c" in html and cards.DRAFT_TEXT not in html
    assert "科技试吃员" in html


def test_evidence_frame_embeds_image_and_numbered_boxes(project, post):
    empty = render_carousel.build_items(project, post, draft=True)[2]["html"]
    assert "待录入截图" in empty
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "a.png", make_png(100, 400))
    write_json(project.post_dir(post) / "highlights.json", {"deepseek": {"prompt_a_screenshot": {"boxes": [{"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.05, "note": "编数据"}], "crop": {"y0": 0, "y1": 0.5}}}})
    html = render_carousel.build_items(project, post, draft=True)[2]["html"]
    assert "data:image/png;base64," in html
    assert html.count('class="hl"') == 1 and 'class="hl-num"' in html
    assert "编数据" in html and "DeepSeek的回答" in html


def test_render_evidence_path_stays_in_this_tools_folder(project, post):
    outside = project.root / "private.png"
    outside.write_bytes(make_png())
    manifest = {"tools": {"deepseek": {"files": {"prompt_a_screenshot": str(outside)}}}}
    assert render_carousel._evidence_path(project, post, manifest, "deepseek", "prompt_a_screenshot") is None
    folder = project.post_dir(post) / "evidence" / "deepseek"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "prompt-a.png").symlink_to(outside)
    manifest["tools"]["deepseek"]["files"]["prompt_a_screenshot"] = project.rel(folder / "prompt-a.png")
    assert render_carousel._evidence_path(project, post, manifest, "deepseek", "prompt_a_screenshot") is None


def test_privacy_masks_are_flattened_before_final_html(project, post, monkeypatch):
    original = make_png(600, 1200, rgb=(240, 20, 20))
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "a.png", original)
    write_json(project.post_dir(post) / "highlights.json", {
        "deepseek": {"prompt_a_screenshot": {"masks": [{"x": 0.01, "y": 0.01, "w": 0.3, "h": 0.1}], "boxes": []}}
    })

    calls = []
    def synthetic_export(pairs, width=1080, height=1440):
        calls.append((width, height))
        for _, destination in pairs:
            destination.write_bytes(make_png(width, height, rgb=(20, 20, 20)))
        return [True] * len(pairs), "synthetic"

    monkeypatch.setattr(render_carousel, "export_many", synthetic_export)
    result = render_carousel.render_post(project, post)
    assert result["status"] == "rendered"
    assert (600, 1200) in calls  # Original-sized screenshot is flattened first.
    html = (project.post_dir(post) / "images" / "03-evidence-deepseek.html").read_text(encoding="utf-8")
    assert base64.b64encode(original).decode("ascii") not in html
    assert base64.b64encode(make_png(600, 1200, rgb=(20, 20, 20))).decode("ascii") in html
    assert "privacy-mask" in html


def test_privacy_mask_export_failure_stops_shareable_output(project, post, monkeypatch):
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "a.png", make_png(600, 1200))
    write_json(project.post_dir(post) / "highlights.json", {
        "deepseek": {"prompt_a_screenshot": {"masks": [{"x": 0.01, "y": 0.01, "w": 0.3, "h": 0.1}]}}
    })
    monkeypatch.setattr(render_carousel, "export_many", lambda pairs, width=1080, height=1440: ([False], "none"))

    with pytest.raises(ProjectError, match="隐私遮挡图生成失败"):
        render_carousel.render_post(project, post)
    assert not list((project.post_dir(post) / "images").glob("*.html"))


def test_meta_line_hides_placeholder_versions():
    line = render_carousel._meta_line({"model": "DeepSeek-V3", "version": "未显示", "platform": "手机 App", "tested_at": "2026-09-28T20:30:00+08:00"})
    assert line == "DeepSeek-V3 · 手机 App · 测试于 2026-09-28"
    assert render_carousel._meta_line({"model": "界面未显示"}) == "模型、版本待录入"


def test_scorecard_and_conclusion_show_human_results_only(project, post):
    complete_post(project, post)
    items = {item["kind"]: item["html"] for item in render_carousel.build_items(project, post, draft=True)}
    assert items["scorecard"].count("✓") >= 20
    assert "改一处就能用" in items["conclusion"]
    assert "“还行”" in items["conclusion"] and "合成测试结论" not in items["conclusion"]  # your own words, not the summary
    fresh = create_post(project, "02")
    blank = {item["kind"]: item["html"] for item in render_carousel.build_items(project, fresh, draft=True)}
    assert "✓" not in blank["scorecard"].split('<div class="legend">')[0]
    assert "待实测" in blank["conclusion"]


def test_render_writes_manifest_and_replaces_old_outputs(project, post, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    first = render_carousel.render_post(project, post)
    images = project.post_dir(post) / "images"
    render = load_json(images / "render.json")
    assert render["draft"] is True and render["png_ok"] is True and len(render["files"]) == 9
    assert all(entry["sha256"] for entry in render["files"])
    create_post(project, "01", force=True, tools=["deepseek", "doubao", "kimi"])
    second = render_carousel.render_post(project, post)
    names = sorted(path.name for path in images.glob("*.png"))
    assert len(names) == 7 and len(second["files"]) == 7
    assert "05-evidence-kimi.png" in names and "06-evidence-yuanbao.png" not in names


def test_every_topic_renders_without_errors(project):
    for topic in project.topics():
        post = create_post(project, topic["id"], slug=f"t{topic['id']}", tools=None)
        items = render_carousel.build_items(project, post, draft=True)
        assert items and items[0]["kind"] == "cover", topic["id"]


def test_real_png_export_when_a_browser_is_available(tmp_path):
    source = tmp_path / "cover.html"
    brand = Project().brand()
    source.write_text(cards.cover_html(tag="5个AI横评", lines=["同一份周报", "谁在瞎编？"], tools=["DeepSeek"], palette=brand["palettes"]["yellow"], account_name="科技试吃员", tagline="测试", draft=True), encoding="utf-8")
    target = tmp_path / "cover.png"
    if not export_html_to_png(source, target):
        pytest.skip("没有可用的无头浏览器（Mac 上装 Google Chrome 即可）")
    assert image_size(target) == (1080, 1440)
