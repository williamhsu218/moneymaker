#!/usr/bin/env python3
"""HTML → PNG export for 1080×1440 post images.

Engines, in order: Playwright (if installed), Google Chrome / Chromium in
headless mode (the usual path on a Mac), wkhtmltoimage. When none is
available the HTML is kept and the caller reports that PNG export failed —
an HTML file is never passed off as a finished image.

The full image set of a post is produced by scripts/render_carousel.py; this
file keeps a small CLI for one-off covers:

    python scripts/generate_post_assets.py --type cover --tag 5个AI横评 \
        --lines 同一份周报 谁在瞎编？ --palette yellow --output /tmp/cover.html --export-png
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import List, Optional, Sequence, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.cards import H, W, cover_html
from scripts.project import Project, write_text

logger = logging.getLogger("generate_post_assets")
MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")


def _chrome_binary() -> Optional[str]:
    if os.path.exists(MAC_CHROME):
        return MAC_CHROME
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _png_ok(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(8) == b"\x89PNG\r\n\x1a\n" and path.stat().st_size > 1000
    except OSError:
        return False


def export_many(pairs: Sequence[Tuple[Union[str, Path], Union[str, Path]]], width: int = W, height: int = H) -> Tuple[List[bool], str]:
    """Export several HTML files to PNG, reusing one browser where possible."""
    jobs = [(Path(src).resolve(), Path(dest).resolve()) for src, dest in pairs]
    for _, dest in jobs:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        results = []
        with sync_playwright() as runner:
            browser = runner.chromium.launch()
            context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
            page = context.new_page()
            for src, dest in jobs:
                try:
                    page.goto(src.as_uri(), wait_until="load")
                    page.wait_for_timeout(120)
                    page.screenshot(path=str(dest))
                    results.append(_png_ok(dest))
                except Exception as exc:  # pragma: no cover - engine specific
                    logger.debug("Playwright export failed for %s: %s", src, exc)
                    results.append(False)
            browser.close()
        if all(results):
            return results, "playwright"
    except Exception as exc:
        logger.debug("Playwright not available: %s", exc)

    chrome = _chrome_binary()
    if chrome:
        results = []
        for src, dest in jobs:
            cmd = [
                chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                f"--window-size={width},{height}", f"--screenshot={dest}", src.as_uri(),
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
            except Exception as exc:  # pragma: no cover
                logger.debug("Chrome export failed: %s", exc)
            results.append(_png_ok(dest))
        if all(results):
            return results, "chrome"

    wkhtml = shutil.which("wkhtmltoimage")
    if wkhtml:
        results = []
        for src, dest in jobs:
            try:
                subprocess.run([wkhtml, "--width", str(width), "--height", str(height), str(src), str(dest)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
            except Exception:  # pragma: no cover
                pass
            results.append(_png_ok(dest))
        return results, "wkhtmltoimage"
    return [False] * len(jobs), "none"


def export_html_to_png(html_path: Union[str, Path], output_png_path: Union[str, Path], width: int = W, height: int = H) -> bool:
    results, _ = export_many([(html_path, output_png_path)], width, height)
    return results[0]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="生成单张 3:4 封面（整套图片请用 render_carousel.py）")
    parser.add_argument("--type", choices=["cover"], default="cover")
    parser.add_argument("--tag", default="5个AI横评")
    parser.add_argument("--lines", nargs="+", default=["同一份周报", "谁在瞎编？"])
    parser.add_argument("--tools", nargs="*", default=["DeepSeek", "豆包", "Kimi", "腾讯元宝", "千问"])
    parser.add_argument("--palette", default="yellow")
    parser.add_argument("--final", action="store_true", help="不加草稿标识（仅用于已复核的内容）")
    parser.add_argument("--output", required=True)
    parser.add_argument("--export-png", action="store_true")
    args = parser.parse_args(argv)
    brand = Project().brand()
    palette = (brand.get("palettes") or {}).get(args.palette)
    if not palette:
        print(f"brand.json 里没有配色 {args.palette}", file=sys.stderr)
        return 2
    out = Path(args.output)
    write_text(out, cover_html(tag=args.tag, lines=args.lines, tools=args.tools, palette=palette, account_name=brand.get("account_name", ""), tagline=brand.get("tagline", ""), style=args.palette, draft=not args.final))
    print(f"HTML：{out}")
    if args.export_png:
        png = out.with_suffix(".png")
        if export_html_to_png(out, png):
            print(f"PNG：{png}")
        else:
            print("PNG 导出失败：没有找到 Chrome/Chromium 或 Playwright。请安装 Google Chrome 后重试。", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
