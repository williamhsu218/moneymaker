#!/usr/bin/env python3
"""
科技试吃员 · 起号工作台一键启动器 (Launch Dashboard CLI).

Features:
- CLI flags: --port [default 8000], --host [default 127.0.0.1], --no-browser, --mock
- Port conflict detection: auto-fallback to available port if 8000 is occupied
- Browser launcher: calls webbrowser.open unless --no-browser
- Graceful shutdown: handles SIGINT (Ctrl+C) and SIGTERM cleanly
- Demo pre-scan: writes clearly labeled demo cards only when --mock is specified
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
import signal
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Union
import webbrowser

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.radar_dashboard import RadarDashboardServer
from scripts.xhs_radar import RadarScanner, DEFAULT_MOCK_DATA
from scripts.ops import ensure_ops_files
from scripts.project import Project

logger = logging.getLogger("launch_dashboard")


def is_port_in_use(host: str, port: int) -> bool:
    """
    Check if a given host:port is currently occupied or unavailable for binding.
    Returns False for port 0 (ephemeral port).
    """
    if port == 0:
        return False

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(host: str, start_port: int, max_attempts: int = 50) -> int:
    """
    Detect port conflicts and auto-fallback to the next available free port.

    If start_port is occupied, scans sequentially start_port+1..start_port+max_attempts-1.
    Logs a user-facing warning when auto-switching ports.
    """
    if start_port <= 0:
        return start_port

    for port in range(start_port, start_port + max_attempts):
        if not is_port_in_use(host, port):
            if port != start_port:
                logger.warning(
                    f"⚠️ 端口 {start_port} 已被占用，已自动切换至空闲端口 {port}"
                )
            return port

    raise RuntimeError(
        f"未能找到可用端口 (扫描范围: {start_port} ~ {start_port + max_attempts - 1})"
    )


def launch_browser(url: str, delay: float = 0.0) -> None:
    """
    Open the given URL in the default system browser after an optional brief delay.
    Runs asynchronously in a background thread to not block server initialization.
    """
    def _open() -> None:
        if delay > 0:
            time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception as exc:
            logger.warning(f"无法自动唤起浏览器: {exc}")

    threading.Thread(target=_open, daemon=True, name="browser-launcher").start()


def prime_mock_data(project_root: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
    """
    Pre-scan explicit demo events into the isolated demo work-order folder.
    """
    resolved_root = Path(project_root).resolve() if project_root else PROJECT_ROOT
    config_file = resolved_root / "scripts" / "radar_sources.json"
    scanner = RadarScanner(config_path=config_file) if config_file.exists() else RadarScanner()
    cards = scanner.scan(
        mock_data=DEFAULT_MOCK_DATA,
        output_dir=resolved_root / "logs" / "radar_actions" / "demo",
    )
    logger.info(f"⚡ [演示预扫描] 已生成 {len(cards)} 张演示工单，均非实时采集")
    return cards


class DashboardLauncher:
    """
    Orchestrates the lifecycle of the local workbench.

    Handles port conflict resolution, mock data priming, browser launch,
    and graceful signal shutdown.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        no_browser: bool = False,
        mock: bool = False,
        project_root: Optional[Union[str, Path]] = None,
    ):
        self.host = host
        self.requested_port = port
        self.actual_port = port
        self.no_browser = no_browser
        self.mock = mock
        self.project_root = Path(project_root).resolve() if project_root else PROJECT_ROOT
        self.server: Optional[RadarDashboardServer] = None
        self.stop_event = threading.Event()

    def prepare(self) -> int:
        """
        Check and resolve port availability, and optionally prime mock data.
        """
        self.actual_port = find_available_port(self.host, self.requested_port)
        ensure_ops_files(Project(self.project_root))
        if self.mock:
            prime_mock_data(self.project_root)
        return self.actual_port

    def start(
        self,
        open_browser_now: bool = True,
        browser_delay: float = 0.0,
    ) -> RadarDashboardServer:
        """
        Start the dashboard HTTP server and optionally trigger browser opening.
        """
        self.prepare()
        self.server = RadarDashboardServer(
            host=self.host,
            port=self.actual_port,
            project_root=self.project_root,
        )
        self.server.start()
        # Retrieve bound port from underlying socket (handles port 0)
        self.actual_port = self.server.port

        url = f"http://{self.host}:{self.actual_port}"
        logger.info(f"🚀 起号工作台已就绪: {url}")

        if not self.no_browser and open_browser_now:
            launch_browser(url, delay=browser_delay)

        return self.server

    def stop(self) -> None:
        """
        Gracefully stop the server and release sockets.
        """
        self.stop_event.set()
        if self.server:
            self.server.stop()
            self.server = None

    def run_forever(self) -> None:
        """
        Start the server and block until interrupted (SIGINT / SIGTERM).
        """
        # Register signal handlers if in main thread
        if threading.current_thread() is threading.main_thread():
            def _signal_handler(sig: int, frame: Any) -> None:
                sig_name = "SIGINT" if sig == signal.SIGINT else "SIGTERM"
                logger.info(f"\n捕获到退出信号 {sig_name}，正在优雅终止服务...")
                self.stop()

            try:
                signal.signal(signal.SIGINT, _signal_handler)
                signal.signal(signal.SIGTERM, _signal_handler)
            except (ValueError, AttributeError):
                pass

        self.start(open_browser_now=True)
        url = f"http://{self.host}:{self.actual_port}"
        print(f"\n=======================================================")
        print(f"🚀 科技试吃员 · 起号工作台已启动: {url}")
        print(f"📂 项目根目录: {self.project_root}")
        print(f"💡 提示: 按 Ctrl+C 可优雅退出服务")
        print(f"=======================================================\n")

        try:
            while not self.stop_event.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            logger.info("用户发起 Ctrl+C，正在退出...")
        finally:
            self.stop()
            print("工作台已停止。")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="launch_dashboard",
        description="科技试吃员 · 起号工作台一键启动",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="绑定的监听地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="监听端口 (默认: 8000，若被占用将自动顺延探测空闲端口)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        default=False,
        help="启动后禁止自动唤起系统浏览器",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="启动时写入明确标记的演示线索工单（不会采集真实信源）",
    )
    return parser


def main(
    argv: Optional[List[str]] = None,
    launcher_out: Optional[List[DashboardLauncher]] = None,
) -> int:
    """
    Main entry point for CLI launcher.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    launcher = DashboardLauncher(
        host=args.host,
        port=args.port,
        no_browser=args.no_browser,
        mock=args.mock,
    )

    if launcher_out is not None:
        launcher_out.append(launcher)

    launcher.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
