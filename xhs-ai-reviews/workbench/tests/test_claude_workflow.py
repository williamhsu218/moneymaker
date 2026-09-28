"""The Claude-in-the-loop layer: suggestions, the xhs.py CLI and who-does-what."""
import io
import json
import sys

import pytest

from conftest import complete_post, fake_export, make_png
from scripts import render_carousel, xhs
from scripts.evidence_intake import save_text
from scripts.new_post import create_post
from scripts.ops import mark_published
from scripts.project import ProjectError, load_json, write_json
from scripts.readiness import assess_post_readiness, review_post
from scripts.suggestions import load_suggestions, note_for, save_suggestions
from scripts.workflow import next_step

POST = "post-01-weekly-report"
SUGGESTION = {"tools": {"deepseek": {"checks": {
    "trap_1": {"value": "fail", "quote": "点击率提升20%", "reason": "效果数据还没出来却写了数字"},
    "trap_2": {"value": "unclear", "reason": ""},
}, "total_score": 3, "verdict": "改两处能交", "summary": "编了点击率"}}}


def run(project, argv, stdin=None, capsys=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = xhs.main(argv, project=project)
    captured = capsys.readouterr()
    return code, (json.loads(captured.out) if captured.out.strip() else None), captured.err


def test_suggestions_are_validated_and_merged(project):
    create_post(project, "01")
    save_text(project, POST, "deepseek", "prompt_a_text", "合成测试回答：点击率提升20%，但效果数据还没出来。")
    save_suggestions(project, POST, SUGGESTION)
    save_suggestions(project, POST, {"tools": {"kimi": {"checks": {"trap_4": {"value": "pass", "reason": "142 字，计划都在"}}}}})
    data = load_suggestions(project, POST)
    assert set(data["tools"]) == {"deepseek", "kimi"} and data["generated_by"].startswith("Claude")
    bad = [
        {"tools": {"chatgpt": {}}},
        {"tools": {"deepseek": {"checks": {"trap_9": {"value": "pass", "reason": "x"}}}}},
        {"tools": {"deepseek": {"checks": {"trap_1": {"value": "maybe"}}}}},
        {"tools": {"deepseek": {"checks": {"trap_1": {"value": "fail"}}}}},
        {"tools": {"deepseek": {"gut_reaction": "替用户写的感受"}}},
        {"tools": {"deepseek": {"total_score": 9}}},
    ]
    for payload in bad:
        with pytest.raises(ProjectError):
            save_suggestions(project, POST, payload)
    assert note_for(SUGGESTION["tools"]["deepseek"]["checks"]["trap_1"]) == "踩坑：效果数据还没出来却写了数字｜原文“点击率提升20%”"


def test_suggestion_quotes_must_come_from_the_transcript(project):
    create_post(project, "01")
    with pytest.raises(ProjectError, match="没有可核对的转写原文"):
        save_suggestions(project, POST, SUGGESTION)
    save_text(project, POST, "deepseek", "prompt_a_text", "4. 活动页上线：已顺利上线，上线首日点击率提升20%。\n5. 下单页卡顿：正在优化中，\n预计下周一完成。")
    ok = {"tools": {"deepseek": {"checks": {
        "trap_1": {"value": "fail", "quote": "上线首日点击率提升20%", "reason": "编了数字"},
        "trap_3": {"value": "fail", "quote": "正在优化中， 预计下周一完成", "reason": "承诺下周一修完"},  # line breaks/spaces don't matter
    }}}}
    save_suggestions(project, POST, ok)
    with pytest.raises(ProjectError, match="找不到"):
        save_suggestions(project, POST, {"tools": {"deepseek": {"checks": {"trap_1": {"value": "fail", "quote": "点击率提升30%", "reason": "编了数字"}}}}})
    save_text(project, POST, "kimi", "prompt_a_text", "这句只出现在 Kimi 的回答里，DeepSeek 没有说过。")
    with pytest.raises(ProjectError, match="本工具转写原文里找不到"):
        save_suggestions(project, POST, {"tools": {"deepseek": {"checks": {"trap_1": {"value": "fail", "quote": "这句只出现在 Kimi 的回答里", "reason": "跨工具引句"}}}}})


def test_gut_reaction_is_required_for_release(project):
    create_post(project, "01")
    complete_post(project, POST)
    scorecard = load_json(project.post_dir(POST) / "scorecard.json")
    scorecard["tool_results"]["kimi"]["gut_reaction"] = ""
    write_json(project.post_dir(POST) / "scorecard.json", scorecard)
    readiness = assess_post_readiness(project, POST, for_review=True)
    details = next(item for item in readiness["blockers"] if item["code"] == "scoring_incomplete")["details"]
    assert details == ["kimi：缺少你自己的一句真实感受"]


def test_next_step_alternates_between_you_and_claude(project, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    create_post(project, "01")
    assert next_step(project, POST)["owner"] == "你"
    (project.post_dir(POST) / "inbox" / "IMG_1.png").write_bytes(make_png())
    step = next_step(project, POST)
    assert step == {"owner": "Claude", "action": "整理 inbox 里的 1 个文件", "say": "第01期截图放好了"}
    (project.post_dir(POST) / "inbox" / "IMG_1.png").unlink()
    complete_post(project, POST)
    scorecard = load_json(project.post_dir(POST) / "scorecard.json")
    for result in scorecard["tool_results"].values():
        result["gut_reaction"] = ""
    write_json(project.post_dir(POST) / "scorecard.json", scorecard)
    assert next_step(project, POST)["owner"] == "Claude"  # no suggestions yet
    save_text(project, POST, "deepseek", "prompt_a_text", "4. 活动页上线：已顺利上线，上线首日点击率提升20%。")
    save_suggestions(project, POST, SUGGESTION)
    step = next_step(project, POST)
    assert "真实感受" in step["action"] and step["then"] == "第01期确认好了"
    complete_post(project, POST)
    copy = project.post_dir(POST) / "copy.md"
    copy.write_text(copy.read_text(encoding="utf-8").replace("## 笔记正文\n", "## 笔记正文\n【一句你自己的真实感受】\n"), encoding="utf-8")
    assert next_step(project, POST) == {"owner": "Claude", "action": "用你确认的结果和感受写定稿", "say": "第01期确认好了"}


def test_published_post_never_asks_to_publish_again(project, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    create_post(project, "01")
    complete_post(project, POST)
    review_post(project, POST, "William")
    render_carousel.render_post(project, POST)
    mark_published(project, POST, "2026-09-28T20:30:00+08:00")
    assert "已发布" in next_step(project, POST)["action"]
    scorecard = load_json(project.post_dir(POST) / "scorecard.json")
    scorecard["tool_results"]["deepseek"]["gut_reaction"] = "修改后的感受"
    write_json(project.post_dir(POST) / "scorecard.json", scorecard)
    assert "已发布" in next_step(project, POST)["action"]


def test_cli_covers_claudes_whole_job(project, capsys, monkeypatch):
    monkeypatch.setattr(render_carousel, "export_many", fake_export)
    code, data, _ = run(project, ["new", "1"], capsys=capsys)
    assert code == 0 and data["post_id"] == POST
    (project.post_dir(POST) / "inbox" / "IMG_0001.PNG").write_bytes(make_png())
    code, data, _ = run(project, ["inbox", POST], capsys=capsys)
    assert data["files"][0]["name"] == "IMG_0001.PNG" and data["files"][0]["pixels"] == "60x120"
    assert "prompt_a_screenshot" in [item["key"] for item in data["targets"]["per_tool"]]
    code, data, _ = run(project, ["file", POST, "IMG_0001.PNG", "deepseek", "prompt_a_screenshot"], capsys=capsys)
    assert data["path"].endswith("evidence/deepseek/prompt-a.png")
    code, data, _ = run(project, ["text", POST, "deepseek", "prompt_a_text", "--source", "claude_transcribed"], stdin="本周工作周报：活动页上线，点击率提升20%。客户高度认可。", capsys=capsys, monkeypatch=monkeypatch)
    manifest = load_json(project.post_dir(POST) / "evidence/manifest.json")
    assert manifest["tools"]["deepseek"]["sources"] == {"prompt_a_screenshot": "inbox", "prompt_a_text": "claude_transcribed"}
    code, data, _ = run(project, ["meta", POST, "deepseek", "model=DeepSeek-V3", "tested_at=2026-09-28T20:30:00+08:00"], capsys=capsys)
    assert data["model"] == "DeepSeek-V3" and data["platform"] == "手机 App" and "关深度思考" in data["settings"]
    code, data, _ = run(project, ["prechecks", POST], capsys=capsys)
    trap1 = next(item for item in data["deepseek"] if item["check"] == "trap_1")
    assert trap1["status"] == "flag" and "20%" in " ".join(trap1["hits"])
    code, data, _ = run(project, ["suggest", POST], stdin=json.dumps(SUGGESTION, ensure_ascii=False), capsys=capsys, monkeypatch=monkeypatch)
    assert data == {"saved": True, "tools": ["deepseek"]}
    code, data, _ = run(project, ["boxes", POST, "deepseek", "prompt_a_screenshot"], stdin=json.dumps({"boxes": [{"x": 0.1, "y": 0.3, "w": 0.8, "h": 0.05, "note": "编数据"}]}), capsys=capsys, monkeypatch=monkeypatch)
    assert data["boxes"] == 1
    code, data, _ = run(project, ["copy", POST], stdin="## 标题候选\n\n1. 同一份周报丢给5个AI，谁在瞎编？\n\n## 笔记正文\n\n【待填】\n", capsys=capsys, monkeypatch=monkeypatch)
    assert data["saved"] and data["errors"]
    code, data, _ = run(project, ["cards", POST], stdin=json.dumps({"photo_captions": {"1": "第1站"}}, ensure_ascii=False), capsys=capsys, monkeypatch=monkeypatch)
    assert data["problems"] == []
    code, data, _ = run(project, ["results", POST], capsys=capsys)
    assert data["tools"]["deepseek"]["model"] == "DeepSeek-V3"
    code, data, _ = run(project, ["render", POST], capsys=capsys)
    assert data["draft"] is True and len(data["files"]) == 9
    code, data, _ = run(project, ["status", POST], capsys=capsys)
    assert data["publishable"] is False and data["next"]["owner"] in ("你", "Claude")
    code, data, _ = run(project, ["metric", POST, "24h", "views=1200", "saves=96"], capsys=capsys)
    assert data["views"] == "1200"
    code, data, _ = run(project, ["request", "测AI写小红书文案"], capsys=capsys)
    assert data["count"] == "1"
    code, data, _ = run(project, ["lead", "title=千问上线视频理解", "url=https://www.qianwen.com", "tool=qianwen"], capsys=capsys)
    assert data["status"] == "待核实"
    code, data, _ = run(project, ["review-week", "1"], capsys=capsys)
    assert data["path"] == "ops/reviews/week-1.md"
    code, data, err = run(project, ["file", POST, "../post.json", "deepseek", "prompt_b_screenshot"], capsys=capsys)
    assert code == 2 and "error" in err


def test_cli_has_no_review_or_publish_command():
    commands = set(xhs.build_parser()._subparsers._group_actions[0].choices)
    assert not commands & {"review", "publish", "published", "mark-published"}
