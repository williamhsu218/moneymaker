# 科技试吃员 · 小红书 AI 工具实测

这个目录保留 Opus 5.5 的两份原始方案，并提供已审计的本地工作台。账号持有人负责真实测试、判断、复核和在小红书 App 内发布；Claude 可协助整理截图、转写、提出判定建议和制作草稿。

## 当前可执行版本

- [工作台与启动说明](workbench/README.md)
- [你与 Claude 的协作流程](workbench/docs/claude_workflow.md)
- [12 期选题和测试标准](workbench/harness/topics.json)
- [优化计划与实施记录](workbench/docs/superpowers/plans/2026-09-27-xhs-platform-optimization.md)

在 `xhs-ai-reviews/workbench/` 目录首次运行：

```bash
python3 scripts/xhs.py new 01
python3 scripts/launch_dashboard.py
```

然后打开 `http://127.0.0.1:8000/`。已有首篇工作区时跳过 `new 01`。工作台使用 Python 标准库和本地前端资源；导出 PNG 图卡需要 Chrome 或 Playwright Chromium。

`posts/`、`ops/` 保存真实截图、回答、账号和运营数据，默认被 Git 忽略，不会随公开仓库发布。请自行备份这两个目录。工作台不会自动发布、评论、回复、点赞或关注。

## 原始参考材料

- [起号启动手册](launch-kit.html) · [原始 artifact](https://claude.ai/artifact/Y9u3WVY4UBufZ9dt8MbLxo)
- [12 期选题手册](topic-handbook.html) · [原始 artifact](https://claude.ai/artifact/CxULGe6mVV39Kd1Un1f5GZ)

两份 HTML 保留原貌，便于追溯方案来源。实际测试规则和流程以工作台的 `harness/topics.json` 与 `docs/claude_workflow.md` 为准。发布时间、涨粉速度、商业合作资格和收益均需用账号实际数据及平台当前提示核实；原始方案中的数字是目标或假设，不是平台承诺。[小红书社区公约 2.0](https://pgy.xiaohongshu.com/help/detail?id=1eda0a065dd894063c2e029a49e8f6a1&userType=4)建议主动说明 AI 辅助参与。
