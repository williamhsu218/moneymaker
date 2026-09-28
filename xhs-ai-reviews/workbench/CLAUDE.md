# 科技试吃员 · 小红书起号项目

处理这个文件夹里的任何请求前，先读 `docs/claude_workflow.md`：它定义了账号持有人和 Claude 的分工、每句口令（「第NN期截图放好了」「第NN期确认好了」「第NN期复核好了」「数据截图放好了」「这周发什么」）对应的步骤，以及 Claude 不能做的事。

- 读写项目文件一律用 `python3 scripts/xhs.py …`，不手改 JSON。
- 真实感受只由账号持有人写；复核和发布只由账号持有人点；Claude 只给建议。
- 修改代码后运行 `python3 -m pytest -q` 和 `node tests/test_frontend_logic.js`。
- 改了 `harness/topics.json` 或 `config/*.json` 后，运行 `python3 scripts/build_prompts.py` 和 `python3 scripts/build_artifact.py`，再把 `artifact/handbook.html` 重新发布到选题手册 artifact（https://claude.ai/artifact/CxULGe6mVV39Kd1Un1f5GZ，带 `url` 更新原链接）。
