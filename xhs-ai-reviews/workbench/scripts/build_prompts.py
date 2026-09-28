#!/usr/bin/env python3
"""Generate harness/prompts/*.md from harness/topics.json.

    python scripts/build_prompts.py          # write all prompt files
    python scripts/build_prompts.py --check  # exit 1 if any file is out of date
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.project import Project, write_text
from scripts.topic_docs import topic_markdown


def build(project: Project, check: bool = False) -> list:
    stale = []
    for topic in project.topics():
        target = project.root / topic["prompt_file"]
        content = topic_markdown(topic, project)
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != content:
            stale.append(str(target.relative_to(project.root)))
            if not check:
                write_text(target, content)
    return stale


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="从 harness/topics.json 生成测试说明")
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    args = parser.parse_args(argv)
    stale = build(Project(), check=args.check)
    if args.check:
        if stale:
            print("以下文件与 topics.json 不一致，请运行 python scripts/build_prompts.py：\n  " + "\n  ".join(stale))
            return 1
        print("测试说明与 topics.json 一致")
        return 0
    print(f"已更新 {len(stale)} 个测试说明" if stale else "测试说明已是最新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
