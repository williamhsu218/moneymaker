"""The config files and the 12-topic data source are complete and consistent."""
import json

from scripts.build_prompts import build
from scripts.project import Project

VALID_IMAGE_KINDS = {"cover", "rules", "evidence_each", "evidence_pair", "evidence_grid", "scorecard", "conclusion", "text_card", "photo"}
VALID_CHECK_TYPES = {"boolean", "enum", "number", "text"}
VALID_EVIDENCE_KINDS = {"text", "image", "file"}


def test_brand_has_voice_palettes_and_account_name():
    brand = Project().brand()
    assert brand["account_name"] == "科技试吃员"
    assert len(brand["bio"]) == 3 and "结论不收钱" in brand["bio"][2]
    assert "评论区点菜" in brand["closer"]
    for name in ("yellow", "dark", "mint"):
        assert {"bg", "ink", "tag_bg", "tag_ink", "accent", "chip_bg", "chip_ink"} <= set(brand["palettes"][name])


def test_tool_links_are_current_and_ids_unique():
    tools = Project().tools()
    ids = [tool["id"] for tool in tools]
    assert len(ids) == len(set(ids))
    urls = " ".join(str(tool.get("web_url")) for tool in tools)
    assert "kimi.moonshot.cn" not in urls and "tongyi.aliyun.com" not in urls
    names = {tool["id"]: tool["display_name"] for tool in tools}
    assert names["qianwen"] == "千问" and names["kimi"] == "Kimi"


def test_twelve_topics_are_complete():
    project = Project()
    topics = project.topics()
    tools = project.tool_map()
    assert [topic["id"] for topic in topics] == [f"{index:02d}" for index in range(1, 13)]
    for topic in topics:
        assert topic["format"] in ("cmp", "how", "new", "recap")
        assert all(tool in tools for tool in topic["tools"]), topic["id"]
        assert len(topic["tools"]) >= topic["min_tools"]
        assert "Gamma" not in json.dumps(topic, ensure_ascii=False)
        for title in topic["titles"]:
            assert len(title) <= 20, (topic["id"], title)
        assert 8 <= len(topic["tags"].split()) <= 10, topic["id"]
        assert "{{opener}}" in topic["body"] and "{{closer}}" in topic["body"]
        for check in topic["checks"].values():
            assert check["type"] in VALID_CHECK_TYPES
            if check["type"] == "enum":
                assert check["options"]
        for bucket in ("per_tool", "shared"):
            keys = [spec["key"] for spec in topic["evidence"][bucket]]
            assert len(keys) == len(set(keys))
            for spec in topic["evidence"][bucket]:
                assert spec["kind"] in VALID_EVIDENCE_KINDS
                if spec["kind"] == "text":
                    assert spec["filename"].endswith(".txt")
        image_keys = {spec["key"] for spec in topic["evidence"]["per_tool"] if spec["kind"] == "image"}
        for image in topic["images"]:
            assert image["kind"] in VALID_IMAGE_KINDS
            if image["kind"] in ("evidence_each", "evidence_pair", "evidence_grid"):
                assert image["key"] in image_keys, (topic["id"], image)
            if image["kind"] == "text_card":
                assert image["card"] in topic.get("cards", {}), (topic["id"], image["card"])
        for pre in topic.get("prechecks", []):
            assert pre.get("check") in topic["checks"], (topic["id"], pre)


def test_weekly_topic_keeps_the_original_prompts_and_traps():
    topic = Project().topic("01")
    prompt_a = topic["tests"][0]["text"]
    assert "效果数据还没出来" in prompt_a and "还没修完" in prompt_a
    assert topic["tests"][1]["text"] == "太长了，压缩到150字以内，下周计划要保留。"
    assert list(topic["checks"]) == ["trap_1", "trap_2", "trap_3", "trap_4"]


def test_recap_topic_requires_ten_verified_posts():
    assert Project().topic("12")["requires_verified_posts"] == 10


def test_generated_prompt_files_match_topics():
    assert build(Project(), check=True) == []
