"""Getting phone screenshots and pasted answers into a post."""
import pytest

from conftest import FAKE_HEIC, make_png
from scripts import evidence_intake
from scripts.evidence_intake import IntakeError, assign_inbox_file, auto_assign, list_inbox, save_text, set_metadata, store_bytes, suggest
from scripts.new_post import create_post
from scripts.project import ProjectError, load_json


@pytest.fixture
def post(project):
    return create_post(project, "01")


def test_saving_a_screenshot_never_moves_the_text_answer(project, post):
    save_text(project, post, "deepseek", "prompt_a_text", "第一轮完整回答原文，足够长。")
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "x.png", make_png())
    folder = project.post_dir(post) / "evidence" / "deepseek"
    assert (folder / "prompt-a.txt").is_file() and (folder / "prompt-a.png").is_file()
    assert not (folder / "_replaced").exists()


def test_replacements_are_archived_not_deleted(project, post):
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "x.png", make_png())
    store_bytes(project, post, "deepseek", "prompt_a_screenshot", "y.png", make_png(rgb=(10, 10, 10)))
    save_text(project, post, "deepseek", "prompt_a_text", "原文第一版，足够长的回答。")
    save_text(project, post, "deepseek", "prompt_a_text", "原文第一版，足够长的回答。")
    save_text(project, post, "deepseek", "prompt_a_text", "原文第二版，内容变了的回答。")
    archived = sorted(path.name for path in (project.post_dir(post) / "evidence" / "deepseek" / "_replaced").iterdir())
    assert len([name for name in archived if name.endswith(".png")]) == 1
    assert len([name for name in archived if name.endswith(".txt")]) == 1


def test_text_is_kept_verbatim_except_line_endings(project, post):
    raw = "第一行\r\n  第二行保留缩进\r\n**加粗也保留**"
    relative = save_text(project, post, "doubao", "prompt_b_text", raw)
    assert (project.root / relative).read_text(encoding="utf-8") == raw.replace("\r\n", "\n")


def test_invalid_scope_key_and_type_are_rejected(project, post):
    with pytest.raises(ProjectError):
        save_text(project, post, "chatgpt", "prompt_a_text", "x" * 20)
    with pytest.raises(ProjectError):
        save_text(project, post, "deepseek", "../../etc", "x" * 20)
    with pytest.raises(IntakeError):
        store_bytes(project, post, "deepseek", "prompt_a_screenshot", "x.png", b"not an image at all" * 20)
    with pytest.raises(IntakeError):
        set_metadata(project, post, "deepseek", {"tested_at": "昨天晚上"})


def test_heic_without_sips_explains_how_to_fix(project, post, monkeypatch):
    monkeypatch.setattr(evidence_intake.shutil, "which", lambda name: None)
    with pytest.raises(IntakeError) as error:
        store_bytes(project, post, "deepseek", "prompt_a_screenshot", "IMG_1.HEIC", FAKE_HEIC)
    assert "兼容性最佳" in str(error.value)


def test_filename_suggestions(project, post):
    assert suggest(project, post, "deepseek-prompt-a.png") == {"scope": "deepseek", "key": "prompt_a_screenshot"}
    assert suggest(project, post, "腾讯元宝-b.jpg") == {"scope": "yuanbao", "key": "prompt_b_screenshot"}
    assert suggest(project, post, "千问_prompt-b.txt") == {"scope": "qianwen", "key": "prompt_b_text"}
    assert suggest(project, post, "IMG_2031.PNG") is None
    math_post = create_post(project, "03")
    assert suggest(project, math_post, "豆包_q2.jpg") == {"scope": "doubao", "key": "q2_screenshot"}


def test_inbox_auto_assign_and_manual_assign(project, post):
    inbox = project.post_dir(post) / "inbox"
    (inbox / "kimi-prompt-a.png").write_bytes(make_png())
    (inbox / "IMG_0001.png").write_bytes(make_png())
    items = {item["name"]: item for item in list_inbox(project, post)}
    assert items["kimi-prompt-a.png"]["suggestion"] == {"scope": "kimi", "key": "prompt_a_screenshot"}
    assigned = auto_assign(project, post)
    assert [item["name"] for item in assigned] == ["kimi-prompt-a.png"]
    assign_inbox_file(project, post, "IMG_0001.png", "kimi", "prompt_b_screenshot")
    manifest = load_json(project.post_dir(post) / "evidence/manifest.json")
    assert set(manifest["tools"]["kimi"]["files"]) == {"prompt_a_screenshot", "prompt_b_screenshot"}
    assert sorted(path.name for path in (inbox / "_imported").iterdir()) == ["IMG_0001.png", "kimi-prompt-a.png"]
    with pytest.raises(IntakeError):
        assign_inbox_file(project, post, "../post.json", "kimi", "prompt_a_screenshot")
