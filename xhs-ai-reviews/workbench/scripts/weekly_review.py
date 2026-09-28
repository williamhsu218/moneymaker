#!/usr/bin/env python3
"""Weekly review from ops/metrics.csv and the calendar.

    python scripts/weekly_review.py --week 1     # writes ops/reviews/week-1.md
    python scripts/weekly_review.py --all        # every week with data

Ratios use the latest checkpoint recorded for each post (7d > 72h > 24h).
Groups with fewer than 3 posts are marked as observations, not patterns.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ops import CHECKPOINTS, load_calendar, load_metrics, top_requests, week_of
from scripts.project import Project, load_json, write_text

FORMAT_NAMES = {"cmp": "横评", "how": "教程", "new": "新品", "recap": "复盘"}
MIN_SAMPLE = 3


def _num(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def latest_rows(project: Project) -> Dict[str, Dict[str, str]]:
    best: Dict[str, Dict[str, str]] = {}
    for row in load_metrics(project):
        current = best.get(row["post_id"])
        rank = CHECKPOINTS.index(row["checkpoint"]) if row["checkpoint"] in CHECKPOINTS else -1
        if current is None or rank >= CHECKPOINTS.index(current["checkpoint"]):
            best[row["post_id"]] = row
    return best


def _published_at(project: Project, post_id: str, row: Dict[str, str]) -> str:
    if row.get("published_at"):
        return row["published_at"]
    for week in load_calendar(project)["weeks"]:
        for slot in week["slots"]:
            if slot.get("post_id") == post_id and slot.get("published_at"):
                return slot["published_at"]
    return ""


def enrich(project: Project) -> List[Dict[str, Any]]:
    posts = []
    for post_id, row in latest_rows(project).items():
        views = _num(row.get("views"))
        saves = _num(row.get("saves"))
        followers = _num(row.get("new_followers"))
        published = _published_at(project, post_id, row)
        palette = ((load_json(project.post_dir(post_id) / "post.json", {}) or {}).get("cover") or {}).get("palette", "")
        posts.append({
            "post_id": post_id,
            "format": row.get("format", ""),
            "checkpoint": row.get("checkpoint"),
            "published_at": published,
            "week": week_of(project, published) if published else None,
            "hour": published[11:13] if len(published) >= 13 else "",
            "palette": palette,
            "views": views, "likes": _num(row.get("likes")), "saves": saves, "comments": _num(row.get("comments")),
            "shares": _num(row.get("shares")), "new_followers": followers, "minutes": _num(row.get("production_minutes")),
            "save_rate": (saves / views) if views and saves is not None else None,
            "follow_rate": (followers / views) if views and followers is not None else None,
        })
    return posts


def _pct(value: Optional[float]) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _group_table(posts: List[Dict[str, Any]], key: str, names: Optional[Dict[str, str]] = None) -> List[str]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for post in posts:
        groups[post.get(key) or "未知"].append(post)
    lines = ["| 分组 | 篇数 | 平均收藏率 | 平均涨粉率 | 说明 |", "| --- | ---: | ---: | ---: | --- |"]
    for name, items in sorted(groups.items()):
        saves = [item["save_rate"] for item in items if item["save_rate"] is not None]
        follows = [item["follow_rate"] for item in items if item["follow_rate"] is not None]
        avg_save = sum(saves) / len(saves) if saves else None
        avg_follow = sum(follows) / len(follows) if follows else None
        note = "样本不足，仅供观察" if len(items) < MIN_SAMPLE else ""
        lines.append(f"| {(names or {}).get(name, name)} | {len(items)} | {_pct(avg_save)} | {_pct(avg_follow)} | {note} |")
    return lines


def review_markdown(project: Project, week: Optional[int]) -> str:
    posts = enrich(project)
    scope = [post for post in posts if week is None or post["week"] == week]
    title = f"第 {week} 周复盘" if week else "累计复盘"
    lines = [f"# {title}", "", "> 由 scripts/weekly_review.py 生成。数据来自 ops/metrics.csv（每篇取最新一次回填）。收藏率 = 收藏 ÷ 浏览，涨粉率 = 新增关注 ÷ 浏览。少于 3 篇的分组只作观察。", ""]
    if not scope:
        lines += ["这一周还没有回填数据。发布后第二天在工作台“发布后数据”里填 24h 数字即可。", ""]
    else:
        lines += ["## 每篇数据", "", "| 篇目 | 形式 | 回填点 | 浏览 | 赞 | 藏 | 评 | 新增关注 | 收藏率 | 涨粉率 | 制作分钟 |", "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for post in sorted(scope, key=lambda item: item["published_at"] or item["post_id"]):
            cells = [post["post_id"], FORMAT_NAMES.get(post["format"], post["format"]), post["checkpoint"]]
            cells += ["—" if post[field] is None else str(post[field]) for field in ("views", "likes", "saves", "comments", "new_followers")]
            cells += [_pct(post["save_rate"]), _pct(post["follow_rate"]), "—" if post["minutes"] is None else str(post["minutes"])]
            lines.append("| " + " | ".join(cells) + " |")
        lines += ["", "## 按形式", ""] + _group_table(scope, "format", FORMAT_NAMES)
        lines += ["", "## 按封面配色", ""] + _group_table(scope, "palette")
        lines += ["", "## 按发布时段（小时）", ""] + _group_table(scope, "hour")
        best = [post for post in scope if post["save_rate"] is not None]
        if best:
            top = max(best, key=lambda item: item["save_rate"])
            lines += ["", f"本周收藏率最高：**{top['post_id']}**（{_pct(top['save_rate'])}）。可以考虑把它的形式或题材放进下周机动位做第二轮。"]
    requests = top_requests(project)
    lines += ["", "## 评论点菜 Top 3", ""]
    lines += [f"- {row['request']}（{row['count']} 次，状态：{row['status']}）" for row in requests] or ["- 还没有记录。评论里有人点菜时，在工作台“点菜清单”里记一笔。"]
    if week == 4:
        lines += ["", "## 下月配比（第 4 周专用）", "", "按上面“按形式”的收藏率和涨粉率调整横评 / 教程 / 新品的篇数；分组少于 3 篇时先保持原配比，再观察一个月。"]
    lines += ["", "## 下周动作", "", "- 【你来填：保留什么、改什么、试什么】", ""]
    return "\n".join(lines)


def write_review(project: Project, week: Optional[int]) -> Path:
    name = f"week-{week}.md" if week else "all.md"
    target = project.ops_dir / "reviews" / name
    write_text(target, review_markdown(project, week))
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成周复盘")
    parser.add_argument("--week", type=int)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    project = Project()
    path = write_review(project, None if args.all or not args.week else args.week)
    print(f"已生成 {path.relative_to(project.root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
