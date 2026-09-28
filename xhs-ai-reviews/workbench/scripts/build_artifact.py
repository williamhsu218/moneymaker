#!/usr/bin/env python3
"""Generate the phone handbook (artifact/handbook.html) from the project config.

The page is the phone companion to the dashboard: while testing in the apps,
the account holder copies prompts and checks the criteria from it. It is
published to the 选题手册 artifact, so it must stay in step with
harness/topics.json, config/brand.json and config/tools.json.

    python scripts/build_artifact.py          # write artifact/handbook.html
    python scripts/build_artifact.py --check  # exit 1 if the page is out of date
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
import sys
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.project import Project, fill_brand_tokens, write_text
from scripts.topic_docs import FORMAT_NAMES, IMAGE_KIND_NAMES

OUTPUT = Path("artifact") / "handbook.html"
PAGE_TITLE = "科技试吃员 选题手册"
GENERATED_NOTE = "<!-- 由 config/*.json 与 harness/topics.json 生成（scripts/build_artifact.py），请改数据源，不要手改本文件。 -->"

# The seven steps from README.md: who does what, and the phrase that starts Claude's part.
WORKFLOW = [
    ("测试", "you", "按本手册的提示词在手机 App 里测，每一轮截一张图，AirDrop 到本期的 inbox 文件夹。", None),
    ("整理证据", "claude", "Claude 看截图、逐字转写、归档，给出带原句的判定建议，标红框，写初稿，出草稿图。", "截图放好了"),
    ("确认判定", "you", "在工作台采纳或修改建议，每个工具写一句真实感受，保存。", None),
    ("文案", "claude", "Claude 用你确认的结果和原话定稿标题、正文、标签和置顶评论。", "确认好了"),
    ("复核", "you", "逐条核对后在工作台点“复核”。只有你能点。", None),
    ("图片", "claude", "Claude 生成终版图，检查发布包。", "复核好了"),
    ("发布与数据", "you", "复制发布包，在 App 里发布，回来标记已发布；数据页截图放进 ops/inbox。", None),
]

RULES = [
    ("ok", "只报告这一次测试", "写清测试日期、版本、免费条件和设置，不说某个工具“一贯更好”。"),
    ("ok", "虚构用例要说明", "周报、PPT 数据、会议剧本都是为测试编的，正文不能写成自己的真实经历。"),
    ("ok", "你的感受只由你写", "每个工具一句真实感受、确认判定、复核和发布都由你完成，Claude 只给建议。"),
    ("ok", "按发布页当前的选项标注 AI 辅助", "只要 Claude 参与了文字就如实选择；不要说勾了标识就不限流。"),
    ("no", "不写没测到的结果", "标题在结果出来前只是方向；带“只推荐1个”“一句话搞定”的标题要结果成立才用。"),
    ("no", "不导流、不留联系方式", "正文、评论和回复里不留微信、二维码、链接，也不提其他平台。"),
    ("no", "不教境外 AI 的访问方法", "只测国内能直接用的 App；传闻、匿名模型和灰度消息只进线索表。"),
    ("no", "截图里的隐私先遮挡", "头像、昵称、真实个人或客户信息先打码，再放进发布图或上传。"),
]

CHECK_KIND_NOTE = {"number": "填数字", "text": "填文字"}
NUMBERED = re.compile(r"^\d+\.\s+")


def esc(text: Any) -> str:
    return html.escape(str(text), quote=True)


def rich(text: Any) -> str:
    """Escape topic HTML snippets, keeping only <b> and <br>."""
    safe = esc(html.unescape(str(text)))
    return (
        safe.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
        .replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>").replace("&lt;br /&gt;", "<br>")
    )


def inline_md(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(text))


def mini_markdown(text: str) -> str:
    """Paragraphs, numbered lists, bullet lists and **bold**: all method_md uses."""
    parts: List[str] = []
    for block in re.split(r"\n\s*\n", str(text).strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if all(NUMBERED.match(line) for line in lines):
            items = "".join("<li>" + inline_md(NUMBERED.sub("", line)) + "</li>" for line in lines)
            parts.append("<ol>" + items + "</ol>")
        elif all(line.startswith("- ") for line in lines):
            items = "".join("<li>" + inline_md(line[2:]) + "</li>" for line in lines)
            parts.append("<ul>" + items + "</ul>")
        else:
            parts.append("<p>" + "<br>".join(inline_md(line) for line in lines) + "</p>")
    return "".join(parts)


class Page:
    """Collects copyable blocks so every copy button points at a unique id."""

    def __init__(self) -> None:
        self.count = 0

    def copy(self, label: str, text: str, ref: str = "") -> str:
        self.count += 1
        block_id = f"c{self.count}"
        ref_html = f'<div class="ref">{rich(ref)}</div>' if ref else ""
        return (
            f'<div class="copy"><div class="copy-top"><span>{esc(label)}</span>'
            f'<button type="button" data-copy="{block_id}">复制</button></div>'
            f'<pre id="{block_id}">{esc(text)}</pre>{ref_html}</div>'
        )


def chip(text: str) -> str:
    return f'<button type="button" class="chip" data-text="{esc(text)}">{esc(text)}</button>'


def week_label(topic: Dict[str, Any]) -> str:
    return "机动位" if not topic.get("week") else f"第{topic['week']}周"


def check_html(check: Dict[str, Any]) -> str:
    kind = check.get("type", "boolean")
    name = f"<b>{esc(check.get('name', ''))}</b>"
    if kind == "boolean":
        lines = []
        if check.get("pass_criteria"):
            lines.append(f'<span class="ok">通过</span>{esc(check["pass_criteria"])}')
        if check.get("fail"):
            lines.append(f'<span class="bad">踩坑</span>{esc(check["fail"])}')
        detail = "<br>".join(lines)
    elif kind == "enum":
        detail = "选一个：" + " / ".join(esc(option) for option in check.get("options", []))
    else:
        bounds = []
        if "min" in check:
            bounds.append(f"最小 {check['min']}")
        if "max" in check:
            bounds.append(f"最大 {check['max']}")
        detail = CHECK_KIND_NOTE.get(kind, "填写") + (f"（{'，'.join(bounds)}）" if bounds else "")
        if check.get("required") is False:
            detail += "（可选）"
    return f"<li>{name}<div class=\"crit\">{detail}</div></li>"


def evidence_html(topic: Dict[str, Any]) -> str:
    evidence = topic.get("evidence") or {}
    items = []
    for bucket, prefix in (("per_tool", "每个工具"), ("shared", "本期共用")):
        for spec in evidence.get(bucket, []):
            flag = "必填" if spec.get("required", True) else "可选"
            items.append(f"<li>{prefix}：{esc(spec.get('label', ''))}<span class=\"flag {'req' if flag == '必填' else ''}\">{flag}</span></li>")
    return f"<ul>{''.join(items)}</ul>" if items else ""


def topic_html(topic: Dict[str, Any], project: Project, brand: Dict[str, Any], page: Page, first: bool = False) -> str:
    number = topic["id"]
    open_attr = " open" if first else ""
    names = [project.tool_name(tool_id) for tool_id in topic.get("tools", [])]
    tools_line = "、".join(esc(name) for name in names) + f"（至少 {topic.get('min_tools', 1)} 款）"
    notes = []
    if topic.get("tools_editable"):
        notes.append("参评工具按本期实际情况改。")
    if topic.get("requires_verified_posts"):
        notes.append(f"至少 {topic['requires_verified_posts']} 期已核验的测试后再做。")
    blocks = [f'<p class="why">{esc(topic.get("why", ""))}</p>']
    blocks.append(
        f'<div class="blk"><h3>参评工具</h3><p>{tools_line}</p>'
        + "".join(f'<p class="muted">{esc(note)}</p>' for note in notes)
        + f'<p class="muted">{esc(topic.get("setup", ""))}</p>'
        + (f'<p class="muted">默认设置：{esc(topic["default_settings"])}</p>' if topic.get("default_settings") else "")
        + "</div>"
    )
    if topic.get("method_md"):
        blocks.append(f'<div class="blk method"><h3>方法与底线</h3>{mini_markdown(topic["method_md"])}</div>')
    if topic.get("tests"):
        tests = "".join(page.copy(test.get("label", test.get("id", "")), test.get("text", ""), test.get("ref", "")) for test in topic["tests"])
        blocks.append(f'<div class="blk"><h3>测试内容（原样复制）</h3>{tests}</div>')
    checks = topic.get("checks") or {}
    if checks:
        overall = topic.get("overall") or {}
        overall_html = f'<p class="muted">另外给一个总分：{esc(overall["label"])}。分数由你判断，不从通过数自动换算。</p>' if overall.get("label") else ""
        blocks.append(f'<div class="blk"><h3>怎么判断（每个工具逐项）</h3><ul class="checks">{"".join(check_html(check) for check in checks.values())}</ul>{overall_html}</div>')
    evidence = evidence_html(topic)
    if evidence or topic.get("assets"):
        assets = "".join(f"<li>{esc(item)}</li>" for item in topic.get("assets", []))
        blocks.append(
            '<div class="blk"><h3>要留存的证据</h3>' + evidence
            + (f'<p class="muted">拍摄提示</p><ul>{assets}</ul>' if assets else "")
            + '<p class="muted">截图 AirDrop 到本期的 inbox 文件夹；回答原文从 App 里复制，不要改动。</p></div>'
        )
    if topic.get("images"):
        items = "".join(
            f'<li><span>{esc(image.get("label", ""))}</span><span class="kind-note">{esc(IMAGE_KIND_NAMES.get(image.get("kind"), image.get("kind", "")))}</span></li>'
            for image in topic["images"]
        )
        video = '<p class="muted">这一期是视频笔记：用剪映把三家同一提示词的视频拼在一起，每段标上工具名；这些图用作封面和结尾。</p>' if topic.get("video") else ""
        blocks.append(f'<div class="blk"><h3>图片顺序（工作台生成）</h3><ol class="imgs">{items}</ol>{video}</div>')
    titles = "".join(f"<li><span>{esc(title)}</span><small>{len(title)}字</small></li>" for title in topic.get("titles", []))
    title_note = f'<p class="warnline">{esc(topic["title_note"])}</p>' if topic.get("title_note") else ""
    blocks.append(f'<div class="blk"><h3>标题备选（结果出来后再选）</h3><ul class="titles">{titles}</ul>{title_note}</div>')
    blocks.append(f'<div class="blk"><h3>正文模板（【 】由测试结果填，感受由你写）</h3>{page.copy("正文", fill_brand_tokens(topic.get("body", ""), brand))}</div>')
    blocks.append(f'<div class="blk"><h3>话题标签</h3>{page.copy("标签", topic.get("tags", ""))}</div>')
    blocks.append(f'<div class="blk"><h3>置顶评论</h3>{page.copy("置顶评论", fill_brand_tokens(topic.get("pin", ""), brand))}</div>')
    if topic.get("extra"):
        blocks.append(f'<p class="note">{esc(topic["extra"])}</p>')
    phrases = "".join(chip(f"第{number}期{phrase}") for _, _, _, phrase in WORKFLOW if phrase)
    blocks.append(f'<div class="blk"><h3>跟 Claude 说（点一下复制）</h3><div class="chips">{phrases}</div></div>')
    kind = topic.get("format", "")
    return (
        f'<details class="topic" id="t{number}"{open_attr}>'
        f'<summary><span class="tno">{number}</span><span class="ttl">{esc(topic.get("name", ""))}</span>'
        f'<span class="kind {esc(kind)}">{esc(FORMAT_NAMES.get(kind, kind))}</span>'
        f'<span class="meta">{week_label(topic)} · 写给{esc(topic.get("audience", ""))} · 工作标题：{esc(topic.get("title", ""))}</span></summary>'
        f'<div class="tbody">{"".join(blocks)}</div></details>'
    )


def schedule_html(topics: List[Dict[str, Any]]) -> str:
    weeks: Dict[int, List[Dict[str, Any]]] = {}
    for topic in topics:
        weeks.setdefault(int(topic.get("week") or 0), []).append(topic)
    rows = []
    for week in sorted(weeks, key=lambda value: (value == 0, value)):
        label = "机动位" if week == 0 else f"第{week}周"
        links = "".join(
            f'<a href="#t{t["id"]}" data-open="t{t["id"]}"><b>{t["id"]}</b>{esc(t.get("name", ""))}</a>' for t in weeks[week]
        )
        rows.append(f'<div class="wk"><span class="wk-label">{label}</span><div class="wk-items">{links}</div></div>')
    return "".join(rows)


def render(project: Project) -> str:
    brand = project.brand()
    doc = project.topics_doc()
    topics = project.topics()
    page = Page()
    workflow = "".join(
        f'<li class="{who}"><div><b>{esc(step)}</b><span class="who {who}">{"你" if who == "you" else "Claude"}</span>'
        f'<span class="muted">{esc(text)}</span>'
        + (f'<span class="say">口令：「第NN期{esc(phrase)}」</span>' if phrase else "")
        + "</div></li>"
        for step, who, text, phrase in WORKFLOW
    )
    rules = "".join(
        f'<div class="rule {kind}"><div><b>{esc(head)}</b><small>{esc(body)}</small></div></div>' for kind, head, body in RULES
    )
    collections = "、".join(f"「{esc(name)}」" for name in brand.get("collections", []))
    cards = "".join(topic_html(topic, project, brand, page, first=index == 0) for index, topic in enumerate(topics))
    toc = "".join(f'<a href="#t{t["id"]}" data-open="t{t["id"]}">{t["id"]}</a>' for t in topics)
    account_name = esc(brand.get("account_name", ""))
    account_note = esc(brand.get("account_name_note", ""))
    opener = esc(brand.get("opener", ""))
    closer = esc(brand.get("closer", ""))
    bio = page.copy("简介", "\n".join(brand.get("bio", [])))
    publish_window = esc(brand.get("publish_window", ""))
    version = esc(doc.get("version", "?"))
    schedule = schedule_html(topics)
    body = f"""{GENERATED_NOTE}
<title>{PAGE_TITLE}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&family=Noto+Sans+SC:wght@400;500;700;900&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header>
  <p class="eyebrow">{account_name} · 手机手册</p>
  <h1>12期怎么测、<mark>怎么发</mark></h1>
  <p class="lead">这是工作台的手机版：在手机 App 里测试时，从这里复制提示词、对照判定标准。内容由工作台的选题数据自动生成，和工作台保持一致。</p>
  <p class="status">目前还没有任何一期的真实测试结果。标题都是测试前的方向，结果出来后再选；只有工作台显示“发布包已放行”才算可以发。</p>
</header>
<nav class="toc" aria-label="目录"><a href="#flow">流程</a><a href="#order">顺序</a><a href="#account">账号</a><a href="#rules">规则</a>{toc}</nav>

<section id="flow">
  <h2>每一期怎么走</h2>
  <ol class="flow">{workflow}</ol>
  <p class="note">每一期你动手的部分：截图、每个工具一句感受、确认判定、点一次复核、发布。Claude 不会替你写感受、复核或发布。每期卡片底部有带期数的口令，点一下就能复制。</p>
</section>

<section id="order">
  <h2>发布顺序</h2>
  <p class="note">首月按每周约 3 篇可验证的内容估算，先做职场题。顺序可以按测试条件和每周数据调整；第12期要等前10期都核验完。</p>
  <div class="weeks">{schedule}</div>
</section>

<section id="account">
  <h2>账号</h2>
  <p>先在工作台“账号”页盘点现有账号（名称、简介、最近10篇的数据），再决定沿用、调整简介还是开新号。旧帖逐篇判断，不批量隐藏，也不删除。</p>
  <div class="facts">
    <div><span class="eyebrow">账号名</span><b>{account_name}</b><small>{account_note}</small></div>
    <div><span class="eyebrow">合集</span><b>{collections}</b></div>
    <div><span class="eyebrow">固定开场</span><b>{opener}</b></div>
    <div><span class="eyebrow">固定结尾</span><b>{closer}</b></div>
  </div>
  {bio}
  <p class="note">发布时间 {publish_window}。涨粉速度、商单门槛和报价都要以账号实际数据和平台当前页面为准。</p>
</section>

<section id="rules">
  <h2>规则</h2>
  <div class="rules">{rules}</div>
</section>

<section id="topics">
  <h2>12期选题</h2>
  <div class="topics">{cards}</div>
</section>

<footer>
  <span>由工作台 harness/topics.json（第 {version} 版）、config/brand.json 和 config/tools.json 生成。改内容请改这些文件，再运行 python3 scripts/build_artifact.py。</span>
  <span>工具的免费额度、功能和名称会变，测试当天在 App 里核对。第5期的身份证号是编的；任何截图里的真实个人信息都要遮挡。</span>
</footer>
</div>
<script>{JS}</script>
"""
    return body


CSS = """
:root {
  --bg: #f1f3ee; --surface: #ffffff; --ink: #16201b; --muted: #56625b; --line: #d3d9d1; --chip: #e3e8e0;
  --accent: #1d6a4d; --accent-soft: #dcebe3; --hl: #f2d34c; --hl-ink: #16201b; --warn: #b3391f; --warn-soft: #f6e1db;
  --f-body: 'IBM Plex Sans', 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  --f-mono: 'IBM Plex Mono', 'Noto Sans SC', ui-monospace, monospace;
  --f-zh: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #0f1311; --surface: #171d1a; --ink: #e3e9e5; --muted: #98a49d; --line: #2b3430; --chip: #222a26;
    --accent: #62c49b; --accent-soft: #1b3129; --hl: #e2c443; --hl-ink: #16201b; --warn: #ee7b62; --warn-soft: #3a211b;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0f1311; --surface: #171d1a; --ink: #e3e9e5; --muted: #98a49d; --line: #2b3430; --chip: #222a26;
  --accent: #62c49b; --accent-soft: #1b3129; --hl: #e2c443; --hl-ink: #16201b; --warn: #ee7b62; --warn-soft: #3a211b;
}
* { box-sizing: border-box; }
body { background: var(--bg); color: var(--ink); font: 400 16px/1.7 var(--f-body); padding-inline: 16px; padding-block: 0 72px; }
.wrap { max-width: 800px; margin: 0 auto; }
h1, h2, h3 { margin: 0; text-wrap: balance; }
p { margin: 0; }
a { color: var(--accent); }
b { font-weight: 700; }
.eyebrow { font: 600 12px/1.3 var(--f-mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }
.muted { color: var(--muted); }
.note { font-size: 14.5px; color: var(--muted); max-width: 62ch; }
header { padding-block: 44px 24px; display: grid; gap: 14px; }
header h1 { font: 900 clamp(34px, 8vw, 54px)/1.12 var(--f-zh); letter-spacing: -.01em; }
header h1 mark { background: var(--hl); color: var(--hl-ink); padding: 0 .12em; border-radius: 3px; }
.lead { font-size: 17px; max-width: 60ch; }
.status { font-size: 14.5px; background: var(--warn-soft); color: var(--warn); border-radius: 8px; padding: 10px 12px; max-width: 62ch; }
nav.toc { position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5; background: var(--bg); padding-block: 10px; border-bottom: 1px solid var(--line); display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; }
nav.toc a { flex: none; text-decoration: none; color: var(--ink); background: var(--chip); font: 600 13px var(--f-mono); padding: 5px 10px; border-radius: 999px; font-variant-numeric: tabular-nums; }
nav.toc a:hover, nav.toc a:focus-visible { background: var(--accent); color: var(--surface); outline: none; }
section { padding-block: 40px 4px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; scroll-margin-top: 56px; }
section > h2 { font: 900 clamp(24px, 5vw, 32px)/1.2 var(--f-zh); }
section > p { max-width: 62ch; }
.flow { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; counter-reset: s; }
.flow li { counter-increment: s; display: grid; grid-template-columns: 32px 1fr; gap: 12px; }
.flow li::before { content: counter(s); font: 700 14px/28px var(--f-mono); text-align: center; width: 28px; height: 28px; border-radius: 50%; border: 1.5px solid var(--accent); color: var(--accent); }
.flow li.claude::before { border-style: dashed; }
.flow li > div { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: baseline; padding-top: 2px; }
.flow .muted { flex-basis: 100%; font-size: 15px; }
.who { font: 600 11.5px var(--f-zh); padding: 1px 7px; border-radius: 4px; }
.who.you { background: var(--hl); color: var(--hl-ink); }
.who.claude { background: var(--accent-soft); color: var(--accent); }
.say { font: 600 13px var(--f-zh); color: var(--accent); }
.weeks { display: grid; gap: 8px; }
.wk { display: grid; grid-template-columns: 64px 1fr; gap: 10px; align-items: start; border-top: 1px solid var(--line); padding-top: 8px; }
.wk-label { font: 600 13px var(--f-zh); color: var(--accent); padding-top: 4px; }
.wk-items { display: flex; flex-wrap: wrap; gap: 6px; }
.wk-items a { text-decoration: none; color: var(--ink); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 4px 10px; font-size: 14.5px; display: inline-flex; gap: 6px; }
.wk-items a b { font: 600 13px var(--f-mono); color: var(--muted); }
.facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.facts > div { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 10px 14px; display: grid; gap: 2px; }
.facts b { font: 700 16px/1.5 var(--f-zh); }
.facts small { color: var(--muted); font-size: 13px; }
.rules { display: grid; gap: 10px; }
.rule { display: grid; grid-template-columns: 22px 1fr; gap: 10px; align-items: start; }
.rule::before { content: ''; width: 12px; height: 12px; margin-top: 7px; border-radius: 2px; background: var(--warn); }
.rule.ok::before { background: var(--accent); border-radius: 50%; }
.rule div { display: grid; gap: 2px; }
.rule small { color: var(--muted); font-size: 14.5px; }
.topics { display: grid; gap: 12px; }
details.topic { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; scroll-margin-top: 60px; }
details.topic[open] { border-color: var(--accent); }
details.topic > summary { list-style: none; cursor: pointer; padding: 14px 16px; display: grid; grid-template-columns: 40px 1fr auto; gap: 2px 12px; align-items: baseline; }
details.topic > summary::-webkit-details-marker { display: none; }
details.topic > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 12px; }
.tno { font: 700 15px var(--f-mono); color: var(--muted); font-variant-numeric: tabular-nums; }
.ttl { font: 700 18px/1.45 var(--f-zh); }
.kind { font: 600 12px var(--f-zh); padding: 2px 8px; border-radius: 4px; background: var(--chip); white-space: nowrap; }
.kind.cmp, .kind.recap { background: var(--hl); color: var(--hl-ink); }
.kind.new { background: var(--warn-soft); color: var(--warn); }
.meta { grid-column: 2 / 4; font-size: 13.5px; color: var(--muted); }
.tbody { padding: 16px 16px 18px; display: grid; gap: 18px; border-top: 1px solid var(--line); }
.blk { display: grid; gap: 8px; }
.blk > h3 { font: 700 13px/1.3 var(--f-zh); color: var(--accent); letter-spacing: .04em; }
.blk p, .blk li { font-size: 15.5px; }
.blk ul, .blk ol { margin: 0; padding-left: 20px; display: grid; gap: 4px; }
.method { background: var(--bg); border-radius: 8px; padding: 12px; }
.method p + p, .method p + ol, .method ol + p { margin-top: 6px; }
.why { font-size: 15.5px; background: var(--accent-soft); border-radius: 8px; padding: 10px 12px; }
.checks { list-style: none; padding: 0 !important; gap: 10px !important; }
.checks li { border-left: 3px solid var(--line); padding-left: 10px; }
.crit { font-size: 14.5px; color: var(--muted); }
.crit .ok, .crit .bad { font: 600 11.5px var(--f-zh); padding: 0 6px; border-radius: 4px; margin-right: 6px; }
.crit .ok { background: var(--accent-soft); color: var(--accent); }
.crit .bad { background: var(--warn-soft); color: var(--warn); }
.flag { font: 600 11px var(--f-zh); margin-left: 6px; padding: 0 6px; border-radius: 4px; background: var(--chip); color: var(--muted); }
.flag.req { background: var(--hl); color: var(--hl-ink); }
.copy { background: var(--bg); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.copy-top { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 6px 6px 6px 12px; border-bottom: 1px solid var(--line); }
.copy-top span { font: 600 12.5px var(--f-zh); color: var(--muted); }
.copy pre { margin: 0; padding: 12px; font: 400 15px/1.8 var(--f-zh); white-space: pre-wrap; word-break: break-word; }
.ref { font-size: 14.5px; color: var(--muted); padding: 8px 12px; border-top: 1px dashed var(--line); word-break: break-word; }
.ref b { color: var(--accent); }
button { font: 600 13px var(--f-zh); color: var(--ink); background: var(--chip); border: 0; border-radius: 7px; padding: 6px 12px; cursor: pointer; }
button:hover { background: var(--accent-soft); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button.done { background: var(--accent); color: var(--surface); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { background: var(--surface); border: 1px solid var(--accent); color: var(--accent); }
.imgs { gap: 6px !important; }
.imgs li { display: flex; justify-content: space-between; gap: 10px; }
.kind-note { font-size: 12.5px; color: var(--muted); white-space: nowrap; }
.titles { list-style: none; padding: 0 !important; gap: 6px !important; }
.titles li { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; font: 700 16px/1.5 var(--f-zh); border-bottom: 1px dashed var(--line); padding-bottom: 6px; }
.titles small { font: 400 12px var(--f-mono); color: var(--muted); white-space: nowrap; }
.warnline { font-size: 14.5px; color: var(--warn); }
footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--line); font-size: 13.5px; color: var(--muted); display: grid; gap: 6px; }
@media (prefers-reduced-motion: no-preference) { html { scroll-behavior: smooth; } }
"""

JS = """
function copyText(text, btn) {
  const label = btn.textContent;
  const done = () => { btn.textContent = '已复制'; btn.classList.add('done'); setTimeout(() => { btn.textContent = label; btn.classList.remove('done'); }, 1400); };
  const fallback = () => {
    const ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    let ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
    ta.remove();
    if (ok) done(); else btn.textContent = '请长按手动复制';
  };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, fallback);
  else fallback();
}
document.addEventListener('click', (e) => {
  const b = e.target.closest('button[data-copy], button[data-text]');
  if (b) copyText(b.dataset.text || document.getElementById(b.dataset.copy).textContent, b);
  const a = e.target.closest('[data-open]');
  if (a) { const d = document.getElementById(a.dataset.open); if (d) d.open = true; }
});
if (/^#t\\d{2}$/.test(location.hash)) { const d = document.querySelector(location.hash); if (d) d.open = true; }
"""


def build(project: Project, check: bool = False) -> bool:
    """Write the page; return True when the file was (or would be) changed."""
    target = project.root / OUTPUT
    content = render(project)
    current = target.read_text(encoding="utf-8") if target.exists() else None
    stale = current != content
    if stale and not check:
        write_text(target, content)
    return stale


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="从 topics.json 和 config 生成手机版手册 artifact/handbook.html")
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    args = parser.parse_args(argv)
    stale = build(Project(), check=args.check)
    if args.check:
        if stale:
            print(f"{OUTPUT} 与数据源不一致，请运行 python scripts/build_artifact.py")
            return 1
        print(f"{OUTPUT} 与数据源一致")
        return 0
    print(f"已更新 {OUTPUT}（发布到选题手册 artifact）" if stale else f"{OUTPUT} 已是最新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
