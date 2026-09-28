"""Render a topic definition from harness/topics.json as readable Markdown.

Used for the generated harness/prompts/*.md files and for each post's README.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

try:
    from scripts.project import Project
except ImportError:  # pragma: no cover - direct execution
    from project import Project

GENERATED_HEADER = "<!-- 由 harness/topics.json 生成（scripts/build_prompts.py），请改 topics.json，不要手改本文件。 -->"
FORMAT_NAMES = {"cmp": "横评", "how": "教程", "new": "新品", "recap": "复盘"}
IMAGE_KIND_NAMES = {
    "cover": "封面", "rules": "规则卡", "evidence_each": "每个工具一张截图框", "evidence_pair": "两家对比",
    "evidence_grid": "多家对比网格", "scorecard": "结果总表", "conclusion": "结论卡", "text_card": "文字卡", "photo": "你拍的照片",
}


def html_to_md(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(text))
    text = re.sub(r"</?b>", "**", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&")


def check_line(check_id: str, check: Dict[str, Any]) -> str:
    kind = check.get("type", "boolean")
    if kind == "boolean":
        detail = f"通过：{check.get('pass_criteria', '—')}；踩坑：{check.get('fail', '—')}"
    elif kind == "enum":
        detail = "选项：" + " / ".join(check.get("options", []))
    elif kind == "number":
        bounds = []
        if "min" in check:
            bounds.append(f"最小 {check['min']}")
        if "max" in check:
            bounds.append(f"最大 {check['max']}")
        detail = "填数字" + (f"（{'，'.join(bounds)}）" if bounds else "")
    else:
        detail = "填文字" + ("（可选）" if check.get("required") is False else "")
    return f"| `{check_id}` | {check.get('name', check_id)} | {detail} |"


def topic_markdown(topic: Dict[str, Any], project: Project, *, for_post: bool = False, post_id: str = "") -> str:
    names = [project.tool_name(tool_id) for tool_id in topic.get("tools", [])]
    lines: List[str] = []
    if not for_post:
        lines += [GENERATED_HEADER, ""]
    heading = f"# 第{topic['id']}期｜{topic.get('name', '')}"
    if for_post:
        heading += "｜测试工作区"
    lines += [heading, ""]
    lines.append(f"- **形式**：{FORMAT_NAMES.get(topic.get('format'), topic.get('format'))}　**写给**：{topic.get('audience', '')}")
    lines.append(f"- **工作标题**：{topic.get('title', '')}")
    lines.append(f"- **参评工具**：{'、'.join(names) if names else '按本期情况填写'}（至少 {topic.get('min_tools', 1)} 款）")
    if topic.get("requires_verified_posts"):
        lines.append(f"- **前提**：至少 {topic['requires_verified_posts']} 期已核验的测试后再做")
    lines += ["", f"> {topic.get('why', '')}", ""]
    if for_post:
        lines += [
            "## 当前状态",
            "",
            "**草稿。** 在工作台（`python scripts/launch_dashboard.py`）里按步骤走：测试 → 录入证据 → 人工评分 → 写文案 → 一键复核 → 生成图片 → 发布后回填数据。",
            "证据、评分、文案都通过复核后，工作台才会放行发布包；复核后任何文件再改动，放行会自动失效，需要重新点一次复核。",
            "",
        ]
    lines += ["## 测试条件", "", topic.get("setup", ""), ""]
    if topic.get("method_md"):
        lines += ["## 方法与底线", "", topic["method_md"], ""]
    if topic.get("tests"):
        lines += ["## 测试内容（原样复制）", ""]
        for test in topic["tests"]:
            lines += [f"### {test.get('label', test.get('id'))}", "", "```text", test.get("text", ""), "```", ""]
            if test.get("ref"):
                lines += [html_to_md(test["ref"]), ""]
    checks = topic.get("checks") or {}
    if checks:
        lines += ["## 怎么判断好坏（每个工具逐项填）", "", "| 键 | 检查项 | 判定 |", "| --- | --- | --- |"]
        lines += [check_line(check_id, check) for check_id, check in checks.items()]
        overall = topic.get("overall") or {}
        if overall:
            lines += ["", f"另填：**{overall.get('label', '总评 1–5')}**、一句话结论、你的第一反应、会不会继续用。分数由你判断，不从通过数自动换算。"]
        lines.append("")
    evidence = topic.get("evidence") or {}
    if evidence.get("per_tool") or evidence.get("shared"):
        lines += ["## 要留存的证据", ""]
        for spec in evidence.get("per_tool", []):
            flag = "必填" if spec.get("required", True) else "可选"
            lines.append(f"- 每个工具：{spec['label']}（{flag}，存为 `evidence/<工具>/{spec['filename']}`{'' if spec['kind'] == 'text' else ' + 扩展名'}）")
        for spec in evidence.get("shared", []):
            flag = "必填" if spec.get("required", True) else "可选"
            lines.append(f"- 本期共用：{spec['label']}（{flag}，存为 `evidence/shared/{spec['filename']}`{'' if spec['kind'] == 'text' else ' + 扩展名'}）")
        lines += ["", "截图用 AirDrop 放进本期的 `inbox/` 文件夹，在工作台里分配给对应工具；PNG、JPG 都可以，HEIC 在 Mac 上会自动转成 PNG。回答原文从 App 里复制后粘贴到工作台，不要改动。", ""]
    if topic.get("assets"):
        lines += ["## 要拍/截的素材", ""] + [f"- {item}" for item in topic["assets"]] + [""]
    if topic.get("images"):
        lines += ["## 图片顺序", ""]
        for index, image in enumerate(topic["images"], 1):
            kind = IMAGE_KIND_NAMES.get(image.get("kind"), image.get("kind"))
            lines.append(f"{index}. {image.get('label', '')}（{kind}）")
        if topic.get("video"):
            lines += ["", "这一期是视频笔记：用剪映把三家同一提示词的视频拼在一起，每段标上工具名；上面几张图用作封面和结尾。"]
        lines.append("")
    lines += ["## 标题备选（结果出来后再选）", ""] + [f"- {title}（{len(title)}字）" for title in topic.get("titles", [])]
    if topic.get("title_note"):
        lines += ["", f"⚠️ {topic['title_note']}"]
    lines.append("")
    if topic.get("extra"):
        lines += ["## 发布提示", "", topic["extra"], ""]
    return "\n".join(lines).rstrip() + "\n"
