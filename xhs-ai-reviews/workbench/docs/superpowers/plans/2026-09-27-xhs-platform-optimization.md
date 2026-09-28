# 科技试吃员｜起号平台评估与优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 把现有“Post-01 防瞎编工作台”升级为能支撑**每周约 3 篇、12 期选题滚动执行**的本地起号平台：证据门槛保留，但手工步骤交给脚本；内容口吻回到小红书原生风格；数据回收和周复盘落盘，便于第 4 周复盘。

**Architecture:** 延续现有 Python 标准库后端（`scripts/radar_dashboard.py`）+ 无构建 Vue 前端（`web/`）。新增 `harness/topics.json`（选题单一数据源）、`config/tools.json`（工具清单）、`ops/`（排期、指标、账号盘点），并把 `/api/post/01` 泛化为 `/api/posts/<post_id>`。

**Tech Stack:** Python 3.12（标准库 + 可选 Playwright 导出 PNG）、Vue 3（本地 vendored）、预编译 CSS、Pytest、Node（前端状态测试）。

**依据：** [启动手册 artifact](https://claude.ai/artifact/Y9u3WVY4UBufZ9dt8MbLxo)、[选题手册 artifact](https://claude.ai/artifact/CxULGe6mVV39Kd1Un1f5GZ)、[执行手册](../../claude_artifact_launch_kit.md)、两份历史 spec/plan。

---

## 执行记录（2026-09-28，P0–P3 已全部落地）

按 P0 → P3 顺序完成 T0–T18。验收：81 项 Python 测试、前端逻辑测试全部通过；在浏览器里用合成数据从“录入证据”走到“发布包已放行”全程跑通（无控制台报错）。

**与计划不同的地方**

| 任务 | 计划 | 实际 | 原因 |
| --- | --- | --- | --- |
| T2 | 把 Vue 和 Tailwind 放进仓库 | 前端改写为原生 JS + 手写 CSS，**零依赖** | 构建环境拿不到 npm 包；改写后也不再有版本和许可证要维护 |
| T3 | 核对各工具 App Store 编号 | 不猜编号：首次运行按名称搜索，在“线索”页确认 | 编号必须以 App Store 实际结果为准 |
| T8 | 新建 3 个 HTML 模板文件 | 所有图片版式集中在 `scripts/cards.py`，旧模板删除 | 一处维护 9 种版式，配色从 brand.json 读 |
| T9 | 04 翻译二选一 | 默认用选题手册的 3 段；harness 那段放进方法说明作备用 | 手册版含中译英潜台词，更能体现专业判断 |
| T10 | 目录名 `posts/02-ppt/` | 保持 `posts/post-02-ppt/` | 与已有的 post-01 一致；`/api/post/01` 保留为兼容别名 |
| T5 | 锁定 22 个文件 | 锁定 20 份证据 + 评分卡、文案、文字卡、红框、篇目设置 + 工具信息摘要 | 图片上出现的内容和模型/版本信息也属于结论 |
| — | — | 生成的图片（`posts/*/images/`）不再进 git | 每次复核后重新生成，避免仓库膨胀 |

**需要你决定或第一次使用时确认**

- 账号名：默认“科技试吃员”（`config/brand.json`），要沿用原昵称就改 `account_name`。
- 第 04 期参考译文：标了“待你定稿”，测试前按你的判断改。
- App Store 监测：在“线索”页点“查找 App 编号”并逐个确认；需要本机网络能访问 itunes.apple.com（本次未在你的网络下实测）。
- 排期：默认从 2026-09-28 起每周一三五 + 周六机动位，日期和选题都可以在“总览 → 编辑排期”里改。
- 工具名称和入口：`config/tools.json` 里 `verified_at` 为空的，测试当天在 App 内核对后填上日期。

---

## 0. 评估结论（2026-09-27 审阅）

### 0.1 一句话

平台**质量扎实、方向偏了**：67 项 Python 测试与前端状态测试全部通过，防编造的“失败即关闭”设计很到位；但它只服务 Post-01，放行需要手工计算 22 个 SHA-256 哈希并手改 JSON，左半屏留给一个只能跑演示数据的雷达。按现状，首篇之后的每一篇都要重新搭一遍，撑不起 3 篇/周。

### 0.2 已经做好、应保留的

| 能力 | 位置 | 说明 |
| --- | --- | --- |
| 发布放行门槛 | `assess_post_01_readiness()` | 评分卡、正文、证据清单、哈希、图卡新鲜度逐项检查，缺一项就不放行 |
| 草稿防误发 | `generate_post_assets.py` | 未核验评分卡自动打“待实测草稿”横幅，空评分卡不会被渲染成五个通过 |
| 雷达诚实降级 | `xhs_radar.py` | 真实采集未接通时明确报错；匿名模型线索不生成测试工单 |
| 本地安全 | `radar_dashboard.py` | 仅本机回环来源可写、资产白名单、路径穿越和软链接防护 |
| 测试套件 | `harness/prompts/*.md` | 12 期都有测试说明；PPT 要求真实导出与复编辑、Excel 有固定数据和正确值，比 artifact 版本更可验证 |
| 测试覆盖 | `tests/` | 放行、草稿、跨域、资产、CLI、前端脏状态都有回归测试 |

### 0.3 主要问题（按对起号的影响排序）

1. **只能做首篇。** 后端路由、放行函数、前端都写死 `post-01-weekly-report`（`app.js` 内 4 处 `/api/post/01`）；02–12 期只有测试说明，没有工作区、文案模板、图片顺序、标签和置顶评论。
2. **放行流程实际上走不通。** 需要手工算 22 个文件的 SHA-256（`radar_dashboard.py:306`），保存评分会强制回到 `draft`（`:808`），界面上没有任何把评分卡设为 `verified` 的入口，只能手改 JSON。证据截图只收 PNG（`:99`），手机长截图常是 JPG/HEIC。
3. **内容口吻丢了。** `copy.md` 变成说明书式正文：没有“我是科技试吃员，新AI我先替你尝一口”开场、没有三个坑的清单、没有“评论区点菜”结尾，标签只剩 4 个（选题手册为 8–10 个）。标题“谁保住了事实？”不是自然的中文说法。
4. **只做了 2 张图，小红书一篇要 6–9 张。** 选题手册的 9 图顺序（封面、规则和 3 个坑、5 张带红框的回答截图、结果总表、结论）里只实现了封面和评分卡。封面主标题只占画面中部约三分之一，信息流缩略图里偏小；只有深色一种配色，artifact 设计的是三种固定配色。
5. **品牌和工具信息不一致。** artifact 建议账号名用“科技试吃员”、“AI试吃员”作合集名；代码与图卡全部写成“AI试吃员”。工具链接过时：Kimi 网页版已是 `kimi.com`，`tongyi.aliyun.com` 现在是通义实验室页面，对话产品是 `qianwen.com`（名称也已是“千问”）。
6. **前端依赖境外 CDN。** `web/index.html:9` 用 Tailwind Play CDN（官方明确不用于生产），`:40` 用 unpkg 的 Vue；这两个在国内网络下经常慢或打不开，打不开时工作台是白屏。
7. **有三份互相矛盾的“内容源”。** 选题手册 artifact、`harness/prompts/`、`topic_matcher.py` 的对照组各说各的：例如 #02 PPT 在 harness 和匹配器里用 Gamma（境外服务，与“只测国内能直接用的 App”原则冲突），选题手册用 Kimi、讯飞智文、WPS AI、AiPPT；#06 匹配器用 ChatPDF/秘塔，#08 用小红书AI/高德AI/百度文心，都与选题手册不同；#03 数学、#04 翻译、#05 Excel、#07 会议、#10 视频的测试题目也不同。
8. **数据只存在浏览器里。** 账号盘点、发布后 24h/72h 数据都存 `localStorage`，只有 Post-01 一份；换浏览器即丢，Claude 也读不到，无法做第 4 周复盘。
9. **雷达占了最好的位置，却不能用。** 左侧 5/12 宽度是只能载入演示数据的雷达；信源以 Arena、Reddit、X 为主，国内访问受限，也偏离“测国内能直接用的 App”的定位。`logs/radar_actions/` 根目录还残留 3 张旧版标题党工单（“把它测穿了”），仍会出现在工单列表。
10. **细节不一致。** 评分卡图例写“🟡 尚可/轻微翻车”，判定逻辑却把 🟡 算作失败（`radar_dashboard.py:65`）；31 个已跟踪文件有未提交改动，另有 10 个新文件（8 份测试套件、前端测试、首篇证据目录）从未纳入版本管理。

### 0.4 与两份 artifact 的覆盖对照

| artifact 建议 | 平台现状 | 缺口 | 对应任务 |
| --- | --- | --- | --- |
| 账号改造：名称、简介、头像、逐步隐藏旧帖、刷新推荐、建 3 个合集 | 仅有账号盘点表单（存浏览器） | 定名未落地、简介文案缺失、盘点不落盘、无改造清单 | T1、T15 |
| 收藏 10 篇高藏对标笔记并分析 | 无 | 无存放和分析位置 | T15 |
| 12 期选题：提示词、判定、素材、图片顺序、标题、正文、标签、置顶评论 | 12 份测试说明；只有 Post-01 工作区 | 02–12 无工作区、无文案模板和图片顺序 | T9、T10、T11 |
| 封面公式：3:4、三种配色、类型在上、大字提问、工具名在下 | 1 个深色封面模板 | 配色单一、标题偏小、无缩略图预览 | T8 |
| 6–9 张图的顺序 | 封面 + 评分卡 | 规则卡、截图框（红框）、结论卡缺失 | T8 |
| Post #1 测试与评分卡（约 45 分钟） | 已实现且更严格 | 放行靠手工哈希，预计 2–3 小时 | T4、T5、T6 |
| 发布规则：AI 声明、第一手、不导流、不教访问境外 AI、不编结果 | 分散在文档中 | 无发布前自动检查 | T7 |
| “你发给我 / 我回给你”的交接 | 无 | 无交接包 | T13 |
| 第 4 周按数据复盘 | 仅 Post-01 的浏览器表单 | 无跨篇指标和复盘 | T14 |
| 48 小时新品实测 | 演示雷达 | 无可用信源 | T17 |

---

## 1. 优化原则

1. **平台不是发帖的前置条件。** Post #1 可以今天就按选题手册测起来；平台改造和发帖并行，P0 只做让首篇更顺的部分。
2. **严谨保留，手工步骤自动化。** 放行门槛不降，哈希、字数、元数据由脚本和表单完成，人只负责“看原文、下判断、点确认”。
3. **一份内容源。** 测试方法和判定以 `harness/` 为准；正文结构、口吻、图片顺序、标签、置顶评论以选题手册为准；两者合并进 `harness/topics.json`，其他地方只读它。
4. **本地、国内网络可用。** 前端依赖全部放进仓库，不依赖任何 CDN。
5. **不做自动运营。** 本工具只做准备工作：不自动发布、不自动评论或回复、不自动点赞关注。发布动作由账号持有人在 App 内完成。平台规则以官方页面和账号内提示为准。
6. **机器预检，人做结论。** 字数统计、数字检测、夸大词提示只是高亮，不自动判定通过或失败。

---

## 2. 里程碑

| 阶段 | 时间 | 目标 | 任务 |
| --- | --- | --- | --- |
| P0 | 第 1–2 天 | 首篇从测试到发布包 ≤ 90 分钟，工作台在国内网络可用 | T0–T8 |
| P1 | 第 1–2 周 | 任一期选题一条命令建好工作区，走同一套流程 | T9–T13 |
| P2 | 第 3–4 周 | 数据落盘，第 4 周能生成复盘 | T14–T16 |
| P3 | 约第 10 篇之后 | 新品线索来源可用，清理历史包袱 | T17–T18 |

工期是估算，按 Claude 执行开发、你负责验收估的。

---

## 3. P0：让首篇顺利发出（第 1–2 天）

### Task 0：存档当前工作区

- [x] `git add -A && git commit -m "chore: checkpoint before optimization plan"`（当前 31 个已跟踪文件有改动，另有 10 个未跟踪的新文件）
- [x] 把 `logs/radar_actions/` 根目录下 3 张旧版工单移到 `logs/radar_actions/legacy/`，`/api/radar/cards` 默认只列 `demo/` 并标注来源

**验收：** `git status` 干净；工单列表里不再出现旧版标题。

### Task 1：定名与品牌常量

**Files:** Create `config/brand.json`；Modify `templates/cover_template.html`、`templates/scorecard_card.html`、`web/index.html`、`scripts/generate_post_assets.py`

- [x] 由你确定：账号名（建议“科技试吃员”或“原昵称｜科技试吃员”）、合集名（AI横评 / AI教程 / 新品实测）、简介三行、固定开场和结尾
- [x] 写入 `config/brand.json`：`account_name`、`series_names`、`bio`、`opener`、`closer`、`palette`（采用 artifact 的三套封面配色：黄底 `#f2d34c`/墨绿字 `#16201b`、深底 `#16201b`/黄字、薄荷底 `#dcebe3`/深绿字 `#133f2e`，强调红 `#e0593b`）
- [x] 模板和前端从 `brand.json` 读取品牌名与配色，删除硬编码的“AI试吃员”“AI试吃员 实测所”

**验收：** 改一次 `brand.json`，封面、评分卡、工作台标题同步变化；新增测试断言模板里没有硬编码品牌名。

### Task 2：前端依赖本地化

**Files:** Create `web/vendor/vue.global.prod.js`、`web/css/app.css`；Modify `web/index.html`

- [x] 把 Vue 3 生产包放进 `web/vendor/`（固定版本号，写进文件头注释）
- [x] 用 Tailwind CLI 按 `index.html` 与 `app.js` 生成一次静态 `web/css/app.css` 并提交；或把用到的工具类改写成少量手写 CSS。两种都不能在运行时依赖网络
- [x] 删除 `cdn.tailwindcss.com` 与 `unpkg.com` 引用
- [x] 新增测试：`web/index.html` 中不得出现 `http://` 或 `https://` 开头的 `<script src>` 和 `<link href>`

**验收：** 断网打开 `python scripts/launch_dashboard.py`，页面完整显示且可交互。

### Task 3：统一工具清单

**Files:** Create `config/tools.json`；Modify `web/js/app.js`、`scripts/radar_sources.json`、`scripts/topic_matcher.py`、`posts/post-01-weekly-report/scorecard.json`

- [x] `tools.json` 每项：`id`（英文目录名，如 `deepseek`）、`display_name`（App 内显示的名称）、`web_url`、`app_name`、`category`、`verified_at`
- [x] 更新名称与链接：Kimi → `https://www.kimi.com`；千问 → 名称“千问”，`https://www.qianwen.com`；DeepSeek、豆包、元宝测试当天再逐一核对
- [x] 工作台“5 款工具直达”、评分卡工具名、证据目录名全部从 `tools.json` 取
- [x] 前端提示：测试以手机 App 为主，网页链接只是备用

**验收：** 全仓库搜索 `kimi.moonshot.cn`、`tongyi.aliyun.com` 无结果；新增测试检查评分卡工具名都在 `tools.json` 中。

### Task 4：证据录入不再手改 JSON

**Files:** Create `scripts/evidence_intake.py`、`tests/test_evidence_intake.py`；Modify `scripts/radar_dashboard.py`、`web/index.html`、`web/js/app.js`

- [x] 新建 `posts/<post_id>/inbox/`（加入 `.gitignore`）：手机截图 AirDrop 进这个文件夹即可
- [x] `evidence_intake.py <post_id>`：按文件名或拍摄时间把截图分配到各工具，接受 PNG/JPG/HEIC（HEIC 在 macOS 上用 `sips` 转 PNG），重命名为 `prompt-a.png` 等；原文件保留在 `inbox/_imported/`
- [x] 工作台每款工具新增：两个文本框粘贴 A/B 原始回答（保存为 `prompt-a.txt`/`prompt-b.txt`，不改动原文）；元数据表单（模型/版本/平台/设置/免费额度/测试时间，时间默认填当前时间）
- [x] `POST /api/posts/<id>/evidence/<tool_id>` 写入文件并更新 `manifest.json`，状态保持 `draft`
- [x] 放行检查接受 PNG/JPG（校验文件头），不再只认 PNG

**验收：** 从空工作区开始，只用工作台和 AirDrop（不打开任何 JSON）就能把 5 款工具的 20 份证据录齐；测试覆盖 JPG 截图与重复导入。

### Task 5：一键复核放行

**Files:** Modify `scripts/radar_dashboard.py`、`web/js/app.js`、`tests/test_radar_dashboard.py`

- [x] 新增 `POST /api/posts/<id>/review`，请求体 `{reviewed_by, confirm: true}`；服务端先跑除哈希外的全部检查，再把评分卡设为 `verified`、计算 22 个文件的 SHA-256 写入 `reviewed_hashes`、填 `reviewed_at`（带时区）和 `claims_reviewed: true`、清单设为 `reviewed`
- [x] 界面按钮“我已逐条对照原文核对”，点击前列出将被锁定的文件；任何被锁文件改动后，界面显示“已失效，需重新核对”，并列出改动的文件
- [x] 保留现有“保存评分即回到草稿”的行为

**验收：** 新增端到端测试：录证据 → 填评分 → 复核 → 放行；改一个字 → 失效 → 再复核 → 放行。README 中“手工计算 SHA-256”的步骤删除。

### Task 6：辅助预检（高亮，不判定）

**Files:** Create `scripts/prechecks.py`、`tests/test_prechecks.py`；Modify `web/js/app.js`

- [x] 陷阱 4：统计 `prompt-b.txt` 字符数（含标点和空格，与 README 口径一致），检测是否同时出现“复盘/PPT”和“卡顿/修”
- [x] 陷阱 1：列出回答里输入中没有的数字和百分比（如“提升20%”）
- [x] 陷阱 2、3：高亮“高度认可、非常满意、一致好评、已修复、已解决、彻底解决”等词
- [x] 结果显示在每款工具评分区旁边，标注“仅供参考，请以原文判断”

**验收：** 用 3 段样例回答（全过、编数字、超字数）测试高亮结果；预检结果不写入 `ratings`。

### Task 7：文案口吻回归与发布前检查

**Files:** Modify `posts/post-01-weekly-report/copy.md`；Create `scripts/publish_lint.py`、`tests/test_publish_lint.py`

- [x] `copy.md` 改用选题手册第 01 期正文结构：固定开场 → 周五写周报的痛点 → 3 个坑的清单 → 结果（✅/❌ 各一行，【】待填）→ 第二轮压缩结果 → 【一句你自己的真实感受】→ 提醒检查数字与进度 → “评论区点菜”结尾
- [x] 标题候选改为提问式、不预设结果、≤20 字，例如：“同一份周报丢给5个AI，谁在瞎编？”“AI写周报会编数据吗？我测了5个”“用AI写周报前，先看这篇”
- [x] 标签恢复为 8–10 个（按实际参评工具取舍）；置顶评论写明测试条件（免费版、新对话、深度思考和联网的开关状态）
- [x] `publish_lint.py <post_id>` 检查：标题 ≤20 字；正文 300–1000 字；标签 8–10 个；无【】占位；无微信/vx/二维码/链接/其他平台名（抖音、B站、公众号等）；无翻墙/VPN/梯子类表述；正文含测试日期或“免费版”等条件说明；输出发布前提醒（在“内容类型声明”中选择 AI 辅助、发布后 1 小时内回复评论）
- [x] 放行检查把 lint 结果纳入阻塞项

**验收：** 草稿 `copy.md` 能列出全部阻塞项；填好的样例正文无阻塞。

### Task 8：首篇整套图片与封面改版

**Files:** Create `templates/rules_card.html`、`templates/screenshot_frame.html`、`templates/conclusion_card.html`、`scripts/render_carousel.py`、`tests/test_render_carousel.py`；Modify `templates/cover_template.html`、`web/index.html`

- [x] 封面按 artifact 公式重做：顶部类型标签、中间一句大字提问（主标题占画面高度 40–55%）、底部工具名；支持三种配色，由 `brand.json` 选择
- [x] 规则卡：原始记录里的 3 个坑 + 第二轮字数要求（左“记录原文”，右“算翻车”）
- [x] 截图框：把 `prompt-a.png` 等比放进 3:4 画布，顶部标工具名和模型版本；支持在 `highlights.json` 里写红框坐标，框出踩坑处
- [x] 结论卡：从已核验评分卡生成“能直接交 X/5 + 一句话”
- [x] `render_carousel.py <post_id>` 按 `topics.json` 的图片顺序输出 `images/01.png…09.png`；未核验时每张都带草稿横幅
- [x] 工作台新增“信息流缩略图预览”：按手机双列宽度（约 1/3 尺寸）并排显示封面，检查标题是否一眼可读
- [x] 评分卡图例改为与判定一致的两态（通过 / 踩坑 / 待评），删除 🟡“尚可”

**验收：** 一条命令生成 9 张 1080×1440 图；缩略图尺寸下主标题可读；测试断言未核验时每张图都带草稿标识。

---

## 4. P1：12 期选题流水线化（第 1–2 周）

### Task 9：选题单一数据源

**Files:** Create `harness/topics.json`、`scripts/build_prompts.py`、`tests/test_topics_schema.py`；Modify `scripts/topic_matcher.py`、`harness/prompts/*.md`

- [x] 从选题手册 artifact 里的 `T` 数组导出 12 期：`why`、`tools`、`setup`、`tests`、`judge`、`assets`、`images`（含“我来做/你来拍”）、`titles`、`titleNote`、`body`、`tags`、`pin`、`extra`
- [x] 合并 harness 的测试方法与判定标准，冲突按下表处理：

| 期 | 冲突 | 处理 |
| --- | --- | --- |
| 02 PPT | harness/匹配器含 Gamma | 改用 Kimi PPT助手、讯飞智文、WPS AI、AiPPT；保留 harness 的“实际导出 + 复编辑”检查 |
| 03 数学 | harness 1 题 + 变式；手册 3 题 | 用手册 3 题（鸡兔同笼、剪绳子、钟表夹角，图更好做）；保留 harness 的“不许用方程 + 验算”判定 |
| 04 翻译 | 原文不同 | 二选一，用你自己更有把握判断的那组；参考译文由你定稿 |
| 05 Excel | 数据与问题不同 | 保留 harness 的固定表与正确值（320 / 2 / 50 / 未找到），补上手册的身份证场景（仅用编造号码） |
| 06 论文 | 匹配器用 ChatPDF/秘塔 | 用手册的 5 款通用 App；保留 harness 的“页码可追溯 + 未研究问题追问” |
| 07 会议 | 剧本不同 | 用手册剧本（两人、预算改口、不请嘉宾），保留 harness 的真值表要求 |
| 08 旅行 | 匹配器用小红书AI/高德AI/文心 | 用手册的千问、豆包、元宝；保留 harness 的“行前核查 ≠ 实地验证” |
| 09 修图 | 工具不同 | 用手册的豆包、元宝、美图秀秀/醒图；保留 harness 的授权和原图哈希要求 |
| 10 视频 | 提示词不同 | 用手册 3 条（人物、液体、中文招牌），信息量更大；保留 harness 的“记录全部尝试” |

- [x] `build_prompts.py` 从 `topics.json` 生成 `harness/prompts/*.md`（文件头标“由 topics.json 生成，勿手改”）
- [x] `topic_matcher.py` 的对照组、封面草案从 `topics.json` 读取，删除内置的 `TOPIC_REGISTRY` 副本
- [x] 在执行手册中注明：选题手册 artifact 只作参考，以 `topics.json` 为准

**验收：** schema 测试：12 期字段齐全，标题 ≤20 字，标签 8–10 个，工具都在 `tools.json` 中；现有匹配测试全部通过。

### Task 10：多篇通用化

**Files:** Create `scripts/new_post.py`、`tests/test_new_post.py`；Modify `scripts/radar_dashboard.py`、`web/js/app.js`、`web/index.html`、全部相关测试

- [x] `python scripts/new_post.py 02` 生成 `posts/02-ppt/`：`README.md`（测试说明）、`copy.md`（正文模板）、`scorecard.json`（该期检查项）、`evidence/manifest.json`、`inbox/`、`images/`
- [x] 路由改为 `/api/posts`、`/api/posts/<id>`、`/api/posts/<id>/scorecard|evidence|review|render`；保留 `/api/post/01` 作为兼容别名一个版本
- [x] `assess_post_01_readiness` 泛化为 `assess_post_readiness(post_dir, topic)`，工具数和证据文件清单来自该期定义，不再写死 5 款、20 份
- [x] 工作台顶部加选题切换器；默认打开排期里“进行中”的那一篇
- [x] 界面重排：左栏改为“本周排期 + 当前一篇的步骤条”，雷达收进可折叠的次要面板

**验收：** 新建 02 和 05 两篇，各自走完录证据、复核、生成图片、lint 的全流程，互不影响；Post-01 的原有测试迁移后全部通过。

### Task 11：按题型定义检查项

**Files:** Modify `harness/topics.json` schema、`scripts/radar_dashboard.py`、`web/js/app.js`

- [x] 检查项支持多种类型：`boolean`（通过/踩坑/待评）、`number`（耗时、字数、步数、花费）、`enum`（PPTX/PDF/图片/导出失败）、`file`（导出的 PPT、视频成品）、`text`
- [x] 每期声明自己的证据文件（如 07 要音频和真值稿，10 要视频原文件），放行按声明检查
- [x] 评分卡模板按检查项类型动态渲染列

**验收：** 02（导出格式、可编辑）和 10（视频文件、等待时长）能按各自检查项生成评分卡。

### Task 12：内容排期

**Files:** Create `ops/calendar.json`、`tests/test_calendar.py`；Modify 工作台

- [x] 字段：`week`、`slot_date`、`post_id`、`format`（横评/教程/新品）、`status`（备题 → 测试中 → 待复核 → 可发布 → 已发布）、`published_at`
- [x] 默认每周 3 个固定位 + 1 个机动位（留给 48 小时新品或上周表现最好题材的第二轮）
- [x] 工作台看板视图，状态由 readiness 自动推进到“可发布”；“已发布”只能由你手动标记

**验收：** 看板显示前 4 周排期，Post-01 状态随证据和复核自动变化。

### Task 13：交接包

**Files:** Create `scripts/handoff.py`；Modify `copy.md` 模板

- [x] 每款工具新增“我的第一反应”（随手写，中英文都可以）和“我会继续用吗”两个字段，对应 artifact 里“Your one-line take”
- [x] `handoff.py <post_id>` 生成 `posts/<id>/handoff.md`：测试条件、评分卡摘要、预检结果、你的原话、证据路径；在 Cowork 里接上这个文件夹，直接说“第 NN 期可以写了”即可，Claude 读这个文件起草标题、正文、红框坐标和置顶评论
- [x] 起草结果只写入 `copy.md` 和 `highlights.json`，最终仍要经过 Task 5 的复核

**验收：** 对一篇已录证据的样例生成完整 `handoff.md`，且不含任何私人信息字段。

---

## 5. P2：数据回收与复盘（第 3–4 周）

### Task 14：指标落盘与周复盘

**Files:** Create `ops/metrics.csv`、`scripts/weekly_review.py`、`tests/test_weekly_review.py`；Modify 工作台（替换 localStorage 复盘表）

- [x] 表头：`post_id,format,published_at,slot,checkpoint(24h|72h|7d),views,likes,saves,comments,shares,new_followers,production_minutes,notes`
- [x] 工作台录入表单写文件，不再只存浏览器；首次打开时把浏览器里已有的 Post-01 数据导入文件
- [x] `weekly_review.py --week N` 生成 `ops/reviews/week-N.md`：按形式、配色、发布时段对比收藏率（收藏/浏览）和涨粉率（新增关注/浏览）；单组少于 3 篇时写“样本不足，仅供观察”
- [x] 第 4 周复盘加一节：下月按收藏率和涨粉率调整三种形式的配比

**验收：** 用 6 篇样例数据生成复盘，比例计算正确，样本不足有提示。

### Task 15：账号盘点与对标笔记落盘

**Files:** Create `ops/account_audit.json`、`ops/benchmarks/README.md`；Modify 工作台

- [x] 账号盘点表单写入 `ops/account_audit.json`（昵称、简介、粉丝数、最近 10 篇的数据、旧帖处理决定）；从浏览器迁移已有草稿
- [x] 增加改造清单：定名、简介、头像、实名认证、每天隐藏 1–2 篇、刷新推荐、建 3 个合集、置顶——逐项勾选并记录日期（昵称 7 天只能改一次，改前以 App 内提示为准）
- [x] `ops/benchmarks/`：放 10 篇高收藏对标笔记的截图，附一张表（标题、封面结构、图片数、收藏数、值得借鉴的地方），供 Claude 分析

**验收：** 盘点数据在重启和换浏览器后仍在；Claude 能直接读取给出旧帖处理建议。

### Task 16：评论点菜清单

**Files:** Create `ops/requests.csv`

- [x] 记录评论里的选题请求：`date,post_id,request,count,status`；每周复盘时汇总最多人点的 3 个，作为机动位候选

**验收：** 周复盘里出现“本周点菜 Top 3”。

---

## 6. P3：新品线索与清理（约第 10 篇之后）

### Task 17：雷达改为国内可用的线索来源

**Files:** Modify `scripts/xhs_radar.py`、`scripts/radar_sources.json`、工作台

- [x] 手动线索：一个表单填链接、一句话描述、“我的 App 里已经能用吗”，存进 `ops/leads.csv`；这是主要入口
- [x] App Store 版本监测：用苹果公开的 iTunes Lookup 接口（`itunes.apple.com/lookup?id=<AppID>&country=cn`）读取 `tools.json` 里各 App 的版本号、更新说明和发布日期，与上次记录比较，有变化就生成一条待核实线索。AppID 在实现时逐一核对
- [x] 官方更新页：DeepSeek 等有公开更新日志的，定时抓取页面对比差异
- [x] 删除 Arena、Reddit、X 层（国内访问受限，匿名模型和社区传闻风险高，与定位不符）；线索永远只进备题，进入测试前必须在自己的账号里确认能用

**验收：** 在本机网络下跑一次真实扫描，能列出各 App 当前版本；接口不可达时明确报错，不回落到演示数据冒充真实结果。

### Task 18：历史文档清理

- [x] 历史 spec/plan 中“自动发布”“黄金一小时撬动算法”“领先官方 3–7 天”等表述改为删除线，并注明不属于现行执行流程
- [x] 执行手册补一节“平台能做什么、不做什么”

---

## 7. 不建议做的事

- 在首篇发布前把 P1、P2 做完。平台是辅助，先发帖、拿到真实数据，比把平台做完整更重要
- 任何代替人发布、评论、回复、点赞、关注的自动化，包括定时发布脚本
- 用浏览器自动化抓小红书站内数据；指标由你从创作者中心手动回填
- 为了抢 48 小时热点跳过真实测试，或让演示数据出现在正式图文里

## 8. 风险与待核实

| 项 | 现状 | 动作 |
| --- | --- | --- |
| 工具名称、入口、免费额度 | 会变 | 每次测试当天核对，记录在证据清单里 |
| 蒲公英开通门槛 | 本次未找到足以确认固定粉丝门槛的官方依据 | 使用合作功能前以 App 内当前准入提示为准 |
| AI 内容标识 | [小红书社区公约 2.0](https://pgy.xiaohongshu.com/help/detail?id=1eda0a065dd894063c2e029a49e8f6a1&userType=4)建议主动说明 AI 辅助参与 | 如实说明创作过程；发布页有内容类型声明时按实际选择 |
| 截图中的个人信息 | 测试用例是编造的，但界面可能出现账号头像和昵称 | 生成截图框时提供打码区域参数 |
| 前端改造回归 | 界面和路由改动较大 | 每个 Task 先写失败的测试，保留 Post-01 兼容别名一个版本 |

## 9. 追加（2026-09-28）：从“记录平台”改成“你 ↔ Claude 协作”

按 P0–P3 做完后试用的反馈：大部分步骤仍要人手工录入，工作台更像事后记录。你不接外部模型 API，希望流程回到 Cowork 里的 Opus 5.5，并且可以手动操作、不追求全自动。据此做了这些改动：

| 改动 | 内容 |
| --- | --- |
| Claude 用的命令行 | `scripts/xhs.py`：状态、inbox、归档、转写、工具信息、预检、判定建议、红框、文案、文字卡、渲染、数据、线索、周复盘；输出 JSON，**没有**复核和发布命令 |
| 判定建议层 | `posts/<篇目>/suggestions.json`：每项给通过/踩坑/看不准，附原句和理由；原句必须能在转写里找到；不能建议“真实感受” |
| 工作台分工 | 7 步都标出“你/Claude”；“确认判定”页可逐项、按工具或一次性采纳建议；每个工具的真实感受必填；顶部“下一步”条给出该说的口令 |
| 流程文档 | `docs/claude_workflow.md`（每句口令对应的步骤和禁止事项），`CLAUDE.md` 指向它 |
| 首篇演练 | 用 10 张合成截图按文档从头跑到“发布包已放行”：转写与原文逐字一致（只差列表符号）；演练中修了预检的 3 处误判/漏判（“尚未修复完成”被当成已修好、下周计划查全文、“预计下周一完成”没有规则）、红框编号挡字、版本“未显示”上图，并把“我的结论”页改为用你的感受原话 |

每篇你动手的部分：截图、每个工具一句感受、确认判定、点一次复核、发布。

---

## 附：本次审阅的核对记录

- 测试：67 项 Python 测试通过；`node tests/test_frontend_state.js` 通过（在仓库副本上运行，没有改动原目录）
- 执行 git 命令时请注意：本机以外的环境访问此仓库时，用 `GIT_OPTIONAL_LOCKS=0 git status`，避免留下 `.git/index.lock`
- 已查看首篇的 `cover.png`、`scorecard.png`，两张都正确带有草稿标识
- 外部信息复核（2026-09-28）：小红书官方《社区公约 2.0》建议主动说明 AI 辅助参与；未找到可靠的一手依据确认固定的蒲公英粉丝门槛、未标识即限流或原计划所述《AI 治理规则公告》的具体措辞，这些表述不作为本工具的发布门槛。
