import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

BASE_URL = "http://192.168.114.149:8124/v1/deepseek"
MODEL = "deepseek-chat"
TIMEOUT = 600
POLL_INTERVAL = 10


def _generate_flag() -> str:
    return secrets.token_hex(4)


def _create_test_config(config_path: Path) -> None:
    config_path.write_text(
        f"[[llm]]\n"
        f'name = "test-native-toolcall"\n'
        f'base_url = "{BASE_URL}"\n'
        f'api_key = "x"\n'
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


def _capture_tmux_output(session_name: str) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-5000"],
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_native_toolcall_tmux_e2e():
    flag = _generate_flag()

    config_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_config_"))
    _create_test_config(config_path)

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
                f"Run the command 'echo {flag}' using process_create tool. Tell me what output you get.",
            ],
            check=True,
        )

        start = time.time()
        while time.time() - start < TIMEOUT:
            if not _tmux_session_exists(session_name):
                output = _capture_tmux_output(session_name)
                if flag in output:
                    return
                pytest.fail(
                    f"linhai exited without reporting flag. Flag: {flag}\nOutput:\n{output}"
                )

            output = _capture_tmux_output(session_name)
            if flag in output:
                return

            time.sleep(POLL_INTERVAL)

        output = _capture_tmux_output(session_name)
        pytest.fail(f"Timeout after {TIMEOUT}s. Flag: {flag}\nOutput:\n{output}")
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
        config_path.unlink(missing_ok=True)
