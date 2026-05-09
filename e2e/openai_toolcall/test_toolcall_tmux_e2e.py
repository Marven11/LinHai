import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

BASE_URL = "http://192.168.114.149:8124/v1"
API_KEY = "gomodel-master-key"
MODEL = "deepseek/deepseek-v4-flash"
TIMEOUT = 600
POLL_INTERVAL = 10


def _generate_flag() -> str:
    return secrets.token_hex(8)


def _create_test_config(config_path: Path) -> None:
    config_path.write_text(
        f"[[llm]]\n"
        f'name = "test-native-toolcall"\n'
        f'base_url = "{BASE_URL}"\n'
        f'api_key = "{API_KEY}"\n'
        f'model = "{MODEL}"\n'
        f"custom_toolcall_format = false\n"
        f"\n"
        f"[[agent]]\n"
        f"compress_threshold = 0.8\n"
        f"\n"
        f"[tools]\n"
        f"max_toolcall_token_in_round = 30000\n"
        f'file_operation_default_rule = "ALLOW"\n'
    )


def _tmux_session_exists(session_name: str) -> bool:
    result = subprocess.run(
        ["tmux", "list-sessions"],
        capture_output=True,
        text=True,
    )
    return session_name in result.stdout


def _tmux_pane_dead(session_name: str) -> bool:
    result = subprocess.run(
        ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_dead}"],
        capture_output=True,
        text=True,
    )
    return "1" in result.stdout


def _capture_tmux_output(session_name: str) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-5000"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_native_toolcall_write_file_e2e():
    flag = _generate_flag()
    config_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_config_"))
    _create_test_config(config_path)
    test_file = Path(f"/tmp/test_native_toolcall_{os.getpid()}.txt")
    session_name = f"test_e2e_{os.getpid()}"

    try:
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "uv",
                "run",
                "python",
                "-m",
                "linhai",
                "--config",
                str(config_path),
                "-m",
                (
                    f"Write a file at path {test_file} containing "
                    f"exactly this text: result={flag}"
                ),
            ],
            check=True,
        )
        subprocess.run(
            ["tmux", "set-option", "-t", session_name, "remain-on-exit", "on"],
            check=False,
        )

        start = time.time()
        last_output = ""
        while time.time() - start < TIMEOUT:
            if test_file.exists():
                content = test_file.read_text()
                if flag in content:
                    return

            if _tmux_pane_dead(session_name):
                break

            if not _tmux_session_exists(session_name):
                break

            last_output = _capture_tmux_output(session_name)
            time.sleep(POLL_INTERVAL)

        if test_file.exists() and flag in test_file.read_text():
            return

        last_output = _capture_tmux_output(session_name)
        pytest.fail(
            f"Native toolcall write file test failed.\n"
            f"Flag: {flag}\n"
            f"File exists: {test_file.exists()}\n"
            f"File content: {test_file.read_text() if test_file.exists() else 'N/A'}\n"
            f"Output:\n{last_output}"
        )
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
        config_path.unlink(missing_ok=True)
        if test_file.exists():
            test_file.unlink()
