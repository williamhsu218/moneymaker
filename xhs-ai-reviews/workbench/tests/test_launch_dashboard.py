"""CLI launcher: argument parsing, port fallback, browser launch, --mock demo cards, shutdown."""
import logging
import socket
import threading
import time
from unittest.mock import patch

import pytest

from scripts.launch_dashboard import (
    DashboardLauncher,
    build_parser,
    find_available_port,
    is_port_in_use,
    launch_browser,
    main,
)


def test_cli_argument_parsing():
    """Test CLI argument parsing defaults and custom options."""
    parser = build_parser()

    # Default arguments
    args = parser.parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.no_browser is False
    assert args.mock is False

    # Custom arguments
    args_custom = parser.parse_args([
        "--host", "0.0.0.0",
        "--port", "8888",
        "--no-browser",
        "--mock",
    ])
    assert args_custom.host == "0.0.0.0"
    assert args_custom.port == 8888
    assert args_custom.no_browser is True
    assert args_custom.mock is True


def test_port_conflict_detection_and_auto_fallback():
    """Test find_available_port detects occupied ports and auto-falls back to next free port."""
    # Bind a temporary socket to simulate port conflict
    dummy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dummy_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    dummy_sock.bind(("127.0.0.1", 0))
    dummy_sock.listen(1)
    busy_port = dummy_sock.getsockname()[1]

    try:
        # Verify port is detected as occupied
        assert is_port_in_use("127.0.0.1", busy_port) is True

        # Call find_available_port starting from occupied port
        free_port = find_available_port("127.0.0.1", start_port=busy_port, max_attempts=10)
        assert free_port > busy_port
        assert is_port_in_use("127.0.0.1", free_port) is False
    finally:
        dummy_sock.close()

    # Test exception raised when max_attempts exceeded
    with patch("scripts.launch_dashboard.is_port_in_use", return_value=True):
        with pytest.raises(RuntimeError, match="未能找到可用端口"):
            find_available_port("127.0.0.1", start_port=8000, max_attempts=5)


def test_browser_launch_behavior():
    """Test browser launcher behavior when --no-browser is or is not set."""
    with patch("webbrowser.open") as mock_open:
        # When launch_browser is invoked directly
        launch_browser("http://127.0.0.1:8000", delay=0.01)
        time.sleep(0.05)
        mock_open.assert_called_with("http://127.0.0.1:8000")

    # When DashboardLauncher starts with no_browser=False
    with patch("webbrowser.open") as mock_open:
        launcher = DashboardLauncher(port=0, no_browser=False)
        server = launcher.start(open_browser_now=True)
        try:
            time.sleep(0.05)
            mock_open.assert_called_once()
            args, _ = mock_open.call_args
            assert f"http://127.0.0.1:{launcher.actual_port}" in args[0]
        finally:
            launcher.stop()

    # When DashboardLauncher starts with no_browser=True
    with patch("webbrowser.open") as mock_open:
        launcher_no_b = DashboardLauncher(port=0, no_browser=True)
        server_no_b = launcher_no_b.start(open_browser_now=True)
        try:
            time.sleep(0.05)
            mock_open.assert_not_called()
        finally:
            launcher_no_b.stop()


def test_dashboard_launcher_with_mock_flag(tmp_path):
    """Test --mock flag triggers mock pre-scan on launcher startup."""
    launcher = DashboardLauncher(port=0, no_browser=True, mock=True, project_root=tmp_path)
    server = launcher.start(open_browser_now=False)
    try:
        assert launcher.actual_port > 0
        client = server.get_test_client()

        # Check action cards were pre-scanned and are immediately available
        res = client.get("/api/radar/cards")
        assert res.status_code == 200
        cards_data = res.json()
        assert cards_data["count"] > 0
        assert len(cards_data["cards"]) > 0
        assert all(card["mode"] == "demo" for card in cards_data["cards"])
    finally:
        launcher.stop()


def test_dashboard_launcher_graceful_shutdown():
    """Test DashboardLauncher handles stop and clean shutdown cleanly."""
    launcher = DashboardLauncher(port=0, no_browser=True)
    server = launcher.start(open_browser_now=False)
    port = launcher.actual_port

    assert server.is_running is True
    launcher.stop()
    assert server.is_running is False

    # Port should now be released and free for reuse
    time.sleep(0.1)
    assert is_port_in_use("127.0.0.1", port) is False


def test_launcher_main_cli_execution():
    """Test main entrypoint execution with --no-browser."""
    # Test help flag raises SystemExit(0)
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0

    # Test quick startup and stop via thread
    launcher_ref = []

    def run_main():
        try:
            main(["--no-browser", "--port", "0"], launcher_out=launcher_ref)
        except Exception as e:
            logging.error(f"Error in main: {e}")

    t = threading.Thread(target=run_main, daemon=True)
    t.start()

    # Wait for launcher to be created and started
    for _ in range(30):
        if launcher_ref and launcher_ref[0].server and launcher_ref[0].server.is_running:
            break
        time.sleep(0.1)

    assert len(launcher_ref) > 0
    launcher = launcher_ref[0]
    assert launcher.server.is_running is True

    # Signal stop
    launcher.stop()
    t.join(timeout=3.0)
    assert not t.is_alive()
