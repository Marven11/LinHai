import os
import subprocess
import tempfile
import time
import uuid as uuid_module
from pathlib import Path

import pytest

BASE_URL = "http://192.168.114.149:8124"
API_KEY = "gomodel-master-key"
MODEL = "deepseek-v4-flash"
TIMEOUT = 600
POLL_INTERVAL = 10


def _generate_uuid() -> str:
    return str(uuid_module.uuid4())


def _create_test_config(config_path: Path) -> None:
    config_path.write_text(
        f"[[llm]]\n"
        f'name = "anthropic-toolcall-e2e"\n'
        f'type = "anthropic"\n'
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


def test_anthropic_toolcall_e2e():
    test_uuid = _generate_uuid()
    config_path = Path(tempfile.mktemp(suffix=".toml", prefix="anthropic_tc_e2e_"))
    _create_test_config(config_path)
    test_file = Path(f"/tmp/anthropic_tc_e2e_{os.getpid()}.txt")
    test_file.write_text(f"The secret UUID for verification is: {test_uuid}\n")
    session_name = f"anthropic_tc_e2e_{os.getpid()}"

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
                    f"Read the file at {test_file} using the read_file tool, "
                    f"then output the complete content of the file."
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
            if _tmux_pane_dead(session_name):
                break

            if not _tmux_session_exists(session_name):
                break

            last_output = _capture_tmux_output(session_name)

            if test_uuid in last_output:
                return

            time.sleep(POLL_INTERVAL)

        last_output = _capture_tmux_output(session_name)
        pytest.fail(
            f"Anthropic toolcall e2e test failed.\n"
            f"UUID: {test_uuid}\n"
            f"Output tail:\n{last_output[-2000:]}"
        )
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
        config_path.unlink(missing_ok=True)
        if test_file.exists():
            test_file.unlink()
