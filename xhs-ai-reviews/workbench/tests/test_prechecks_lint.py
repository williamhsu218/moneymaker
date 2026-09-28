"""Assistive pre-checks and blocking publish checks."""
import pytest

from scripts.evidence_intake import save_text
from scripts.new_post import create_post
from scripts.prechecks import check_char_count, check_keywords, check_must_include, check_new_numbers, cn_to_int, run_prechecks
from scripts.project import Project
from scripts.publish_lint import lint_cards, lint_copy, parse_copy

GOOD_B = "本周：活动页三版定稿并上线，数据待回收；客户基本认可，几处待确认；卡顿已定位为图片过大，修复中。下周：继续修卡顿，准备月底复盘PPT。"


def hints(report, tool, check):
    return [item for item in report["results"][tool] if item["check"] == check]


def test_weekly_prechecks_flag_fabrication_and_pass_clean_answers(project):
    post = create_post(project, "01")
    save_text(project, post, "deepseek", "prompt_a_text", "1. 活动页上线，点击率提升20%。\n2. 客户高度认可方案。\n3. 卡顿问题已修复。")
    save_text(project, post, "deepseek", "prompt_b_text", GOOD_B + "另外" * 60)
    save_text(project, post, "doubao", "prompt_a_text", "1. 双11活动页三版定稿，周一和设计对齐。\n2. 客户觉得还行，几处待确认。\n3. 卡顿原因已找到，下周一继续修。")
    save_text(project, post, "doubao", "prompt_b_text", GOOD_B)
    report = run_prechecks(project, post)
    numbers = hints(report, "deepseek", "trap_1")[0]
    assert numbers["status"] == "flag" and [hit["match"] for hit in numbers["hits"]] == ["20%"]
    assert hints(report, "deepseek", "trap_2")[0]["status"] == "flag"
    assert hints(report, "deepseek", "trap_3")[0]["status"] == "flag"
    assert any(item["status"] == "flag" for item in hints(report, "deepseek", "trap_4"))
    assert all(item["status"] == "ok" for check in ("trap_1", "trap_2", "trap_3", "trap_4") for item in hints(report, "doubao", check)), report["results"]["doubao"]
    assert all(item["status"] == "missing" for item in report["results"]["kimi"])


def test_prechecks_skip_negations_scope_the_plan_and_catch_promises(project):
    """Cases found in the post-01 dry run: “尚未修复完成”, a plan that drops 卡顿, “预计下周一完成”."""
    post = create_post(project, "01")
    save_text(project, post, "qianwen", "prompt_a_text", "下单页卡顿原因已找到，为图片过大，尚未修复完成，下周一继续处理。")
    save_text(project, post, "qianwen", "prompt_b_text", GOOD_B)
    save_text(project, post, "yuanbao", "prompt_a_text", "排查下单页卡顿问题，确认原因为图片过大，问题已解决。")
    save_text(project, post, "yuanbao", "prompt_b_text", "本周：推送文案已交运营；下单页卡顿（图片过大）已解决。下周：准备月底复盘PPT。")
    save_text(project, post, "deepseek", "prompt_a_text", "下单页卡顿：已定位原因为图片过大，正在优化中，预计下周一完成。")
    report = run_prechecks(project, post)
    qianwen = hints(report, "qianwen", "trap_3")
    assert all(item["status"] == "ok" for item in qianwen) and "尚未修复完成" in qianwen[0]["detail"]
    assert hints(report, "yuanbao", "trap_3")[0]["status"] == "flag"
    plan = next(item for item in hints(report, "yuanbao", "trap_4") if item["type"] == "must_include")
    assert plan["status"] == "flag" and "卡顿" in plan["detail"] and "下周" in plan["detail"]
    assert next(item for item in hints(report, "qianwen", "trap_4") if item["type"] == "must_include")["status"] == "ok"
    promise = next(item for item in hints(report, "deepseek", "trap_3") if item["type"] == "regex")
    assert promise["status"] == "flag" and promise["hits"][0]["match"] == "预计下周一完成"
    assert next(item for item in qianwen if item["type"] == "regex")["status"] == "ok"  # “下周一继续处理” is fine


def test_keyword_and_scope_helpers():
    assert check_keywords({"a": "还没解决，未能修复完成"}, ["已解决", "修复完成", "解决"])["status"] == "ok"
    assert check_keywords({"a": "问题已解决"}, ["已解决"])["status"] == "flag"
    fallback = check_must_include("卡顿修复中，准备PPT", [["卡顿"]], after=["下周计划"])
    assert fallback["status"] == "ok" and "按全文查" in fallback["detail"]


def test_number_and_char_helpers():
    assert cn_to_int("十一") == 11 and cn_to_int("三") == 3 and cn_to_int("一百五十") == 150
    assert check_new_numbers({"a": "双11已上线，改了3版"}, "双十一活动页，改了三版")["status"] == "ok"
    assert check_new_numbers({"a": "转化率 12.5%"}, "效果数据还没出来")["hits"][0]["match"] == "12.5%"
    counts = check_char_count("  **标题**\n正文 一二  ", 150)["counts"]
    assert counts == {"with_spaces": 12, "without_spaces": 10, "without_markdown": 6}


def test_math_equation_detector(project):
    post = create_post(project, "03")
    save_text(project, post, "kimi", "q1_text", "设鸡有x只，兔有y只，x+y=35，2x+4y=94，所以鸡23只兔12只。")
    report = run_prechecks(project, post)
    assert hints(report, "kimi", "q1_no_equation")[0]["status"] == "flag"
    assert hints(report, "kimi", "q1_correct")[0]["status"] == "ok"


def filled_copy(**overrides):
    parts = {
        "title": "同一份周报丢给5个AI，谁在瞎编？",
        "body": "我是科技试吃员，新AI我先替你尝一口🍴\n" + "测试内容" * 80 + "\n测试条件：9月28日，免费版\n想让我试吃什么，评论区点菜👇",
        "tags": "#AI工具 #AI测评 #周报 #打工人 #职场干货 #效率工具 #DeepSeek #豆包",
        "pin": "测试统一用的免费版～",
    }
    parts.update(overrides)
    return f"# 第01期\n\n> 草稿说明：【这里是说明，不检查】\n\n## 标题候选\n\n1. {parts['title']}\n2. 备选标题\n\n## 笔记正文\n\n{parts['body']}\n\n## 推荐标签\n\n{parts['tags']}\n\n## 首评置顶\n\n{parts['pin']}\n\n## 发布前核对\n\n- [x] 已核对\n"


def test_clean_copy_passes_and_blockquotes_are_ignored():
    report = lint_copy(filled_copy(), Project().brand())
    assert report["ok"] is True, report["errors"]
    assert report["warnings"] == []
    assert parse_copy(filled_copy())["titles"][0] == "同一份周报丢给5个AI，谁在瞎编？"


@pytest.mark.parametrize("override, code", [
    ({"title": "这是一个超过二十个字的标题，肯定会被拦下来的"}, "title_too_long"),
    ({"body": "结论是【待填】" + "字" * 300}, "placeholder"),
    ({"pin": "想要资料加微信领取"}, "off_platform"),
    ({"body": "我是科技试吃员" + "字" * 300 + "详情看 https://example.com"}, "link"),
    ({"body": "我是科技试吃员" + "字" * 300 + "电话13812345678"}, "phone"),
    ({"body": "我是科技试吃员" + "字" * 300 + "需要科学上网才能用"}, "vpn"),
    ({"tags": "#AI工具 #待实测"}, "draft_marker"),
])
def test_blocking_errors(override, code):
    report = lint_copy(filled_copy(**override), Project().brand())
    assert report["ok"] is False
    assert code in {item["code"] for item in report["errors"]}


def test_style_warnings():
    report = lint_copy(filled_copy(body="短正文", tags="#AI", pin="你们用哪个？"), Project().brand())
    warning_codes = {item["code"] for item in report["warnings"]}
    assert {"body_length", "tag_count", "opener", "closer", "conditions"} <= warning_codes
    assert report["ok"] is True


def test_card_placeholders_block():
    assert lint_cards({"tips": {"title": "建议", "lines": ["1. 【待填】"]}, "photo_captions": {"1": "第1站【地点】"}})
    assert lint_cards({"tips": {"title": "建议", "lines": ["都填好了"]}, "photo_captions": {}}) == []
