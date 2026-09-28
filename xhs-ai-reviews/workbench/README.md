# 科技试吃员 · 小红书起号工作台

本地工作台，把“本人实测 → 留存证据 → 人工判断 → AI 辅助整理 → 复核后发布 → 数据复盘”串成一条流程。它只做准备工作：**不会替你发布、评论或回复**，发布永远由你在小红书 App 里完成。

- 起号计划与规则：[docs/claude_artifact_launch_kit.md](docs/claude_artifact_launch_kit.md)
- 优化方案与执行记录：[docs/superpowers/plans/2026-09-27-xhs-platform-optimization.md](docs/superpowers/plans/2026-09-27-xhs-platform-optimization.md)
- 手机版手册（测试时在手机上复制提示词、对照判定标准）：[选题手册 artifact](https://claude.ai/artifact/CxULGe6mVV39Kd1Un1f5GZ)，由 `artifact/handbook.html` 发布

## 启动

```bash
python3 scripts/xhs.py new 01                   # 首次使用：建立第 01 期本地工作区
python3 scripts/launch_dashboard.py             # 打开 http://127.0.0.1:8000
```

已有 `posts/post-01-weekly-report/` 时跳过第一行。只用 Python 标准库，页面不依赖任何 CDN，断网也能打开。生成 PNG 图片需要本机装有 Google Chrome（或 `pip install playwright && playwright install chromium`）。`posts/` 和 `ops/` 的真实截图、回答、账号及指标数据只留在本机，不纳入 Git；备份时请自行保存这两个目录。

## 每一期怎么走（你 ↔ Claude）

在 Cowork 里接上这个文件夹，Claude（Opus 5.5）按 [docs/claude_workflow.md](docs/claude_workflow.md) 做整理、判卷建议和写稿；工作台是你查看、确认和复核的地方。

| 步骤 | 谁 | 做什么 |
| --- | --- | --- |
| 1 测试 | 你 | 按工作台“测试”页的提示词在手机 App 里测，每轮截一张图，AirDrop 到 `posts/<篇目>/inbox/` |
| 2 整理证据 | Claude | 你说「第NN期截图放好了」：Claude 看截图、逐字转写、归档、填模型和时间，给出判定建议、标红框、写初稿、出草稿图 |
| 3 确认判定 | 你 | 工作台里采纳或修改建议，每个工具写一句真实感受，保存 |
| 4 文案 | Claude | 你说「第NN期确认好了」：Claude 用你确认的结果和原话定稿标题、正文、标签、置顶评论 |
| 5 复核 | 你 | 逐条核对后点“复核”（只能你点） |
| 6 图片 | Claude | 你说「第NN期复核好了」：生成终版图，检查发布包 |
| 7 发布与数据 | 你 | 复制发布包去 App 发布，回来标记已发布；数据页截图放进 `ops/inbox/`，说「数据截图放好了」 |

每篇你动手的部分：截图、每个工具一句感受、确认判定、点一次复核、发布。Claude 不会替你写感受、不会替你复核或发布。

## 目录

| 路径 | 内容 |
| --- | --- |
| `config/brand.json` | 账号名、简介、开场/结尾、封面配色 |
| `config/tools.json` | 工具 id、显示名、网页链接、App Store 搜索词 |
| `harness/topics.json` | 12 期选题的唯一数据源（测试内容、判定、证据、图片顺序、正文模板、标签） |
| `harness/prompts/*.md` | 由 `scripts/build_prompts.py` 从 topics.json 生成，勿手改 |
| `artifact/handbook.html` | 手机版手册，由 `scripts/build_artifact.py` 从 config 和 topics.json 生成，勿手改；发布到选题手册 artifact |
| `posts/<篇目>/` | 每期工作区：`copy.md`、`scorecard.json`、`evidence/`、`inbox/`、`images/`、`photos/` |
| `ops/` | 排期、发布后数据、账号盘点、评论点菜、对标笔记、新品线索、周复盘 |
| `scripts/` | 服务端与命令行工具（见下） |
| `web/` | 工作台页面（原生 JS + 手写 CSS） |

## 命令行

```bash
python3 scripts/xhs.py --help                                           # Claude 用的统一命令（状态、归档、转写、建议、红框、文案、渲染、数据）
python scripts/new_post.py 11 --slug qwen-omni --tools qianwen doubao   # 新建工作区
python scripts/evidence_intake.py post-01-weekly-report --auto          # 按文件名归档 inbox
python scripts/prechecks.py post-01-weekly-report                       # 预检
python scripts/publish_lint.py post-01-weekly-report                    # 发布前检查
python scripts/render_carousel.py post-01-weekly-report                 # 生成整套图片
python scripts/handoff.py post-01-weekly-report                         # 给 Claude 的交接包
python scripts/weekly_review.py --week 1                                # 周复盘
python scripts/xhs_radar.py --appstore-resolve | --appstore-check | --official-check
python scripts/build_prompts.py [--check]                               # 由 topics.json 生成测试说明
python scripts/build_artifact.py [--check]                              # 由 config 和 topics.json 生成手机版手册
```

## 测试

```bash
.venv/bin/pytest -q
node tests/test_frontend_logic.js
```
