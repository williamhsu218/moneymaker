"""Scaffolding a post workspace from a topic."""
import pytest

from scripts.new_post import create_post
from scripts.project import ProjectError, load_json


def test_scaffold_creates_every_file(project):
    post_id = create_post(project, "01")
    assert post_id == "post-01-weekly-report"
    post_dir = project.post_dir(post_id)
    for name in ("post.json", "README.md", "copy.md", "scorecard.json", "cards.json", "highlights.json", "evidence/manifest.json"):
        assert (post_dir / name).is_file(), name
    for folder in ("inbox", "images", "photos"):
        assert (post_dir / folder).is_dir()
    scorecard = load_json(post_dir / "scorecard.json")
    assert scorecard["status"] == "draft"
    assert scorecard["tools"] == ["deepseek", "doubao", "kimi", "yuanbao", "qianwen"]
    assert set(scorecard["checks"]) == {"trap_1", "trap_2", "trap_3", "trap_4"}
    manifest = load_json(post_dir / "evidence/manifest.json")
    assert manifest["status"] == "draft" and manifest["claims_reviewed"] is False
    assert set(manifest["tools"]) == set(scorecard["tools"])


def test_copy_template_uses_the_brand_voice(project):
    post_id = create_post(project, "01")
    copy = (project.post_dir(post_id) / "copy.md").read_text(encoding="utf-8")
    assert "我是科技试吃员，新AI我先替你尝一口" in copy
    assert "评论区点菜" in copy
    assert "{{opener}}" not in copy and "{{closer}}" not in copy
    for heading in ("## 标题候选", "## 笔记正文", "## 推荐标签", "## 首评置顶", "## 发布前核对"):
        assert heading in copy
    assert "【" in copy  # results are still placeholders


def test_refuses_duplicates_unknown_tools_and_too_few_tools(project):
    create_post(project, "02")
    with pytest.raises(ProjectError):
        create_post(project, "02")
    with pytest.raises(ProjectError):
        create_post(project, "11", slug="x", tools=["no_such_tool"])
    with pytest.raises(ProjectError):
        create_post(project, "01", slug="solo", tools=["deepseek"])
    with pytest.raises(ProjectError):
        create_post(project, "11", slug="Bad Slug")


def test_new_release_can_have_several_workspaces(project):
    first = create_post(project, "11", slug="qwen-omni", tools=["qianwen", "doubao"])
    second = create_post(project, "11", slug="kimi-update", tools=["kimi"])
    assert first != second
    assert project.list_posts() == sorted([first, second])
    assert load_json(project.post_dir(first) / "post.json")["tools"] == ["qianwen", "doubao"]
