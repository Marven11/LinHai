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
    return secrets.token_hex(8)


def _create_test_config(config_path: Path, secret_path: str) -> None:
    config_path.write_text(
        f"[[llm]]\n"
        f'name = "test-secret"\n'
        f'base_url = "{BASE_URL}"\n'
        f'api_key = "x"\n'
        f'model = "{MODEL}"\n'
        f"custom_toolcall_format = true\n"
        f"\n"
        f"[[agent]]\n"
        f"compress_threshold = 0.8\n"
        f"[agent.secret]\n"
        f'config_path = "{secret_path}"\n'
        f"\n"
        f"[tools]\n"
        f"max_toolcall_token_in_round = 30000\n"
        f'file_operation_default_rule = "ALLOW"\n'
    )


def _create_secret_config(secret_path: Path, flag: str) -> None:
    secret_path.write_text(
        f"[secrets]\n"
        f"[secrets.TEST_API_KEY]\n"
        f'value = "sk-test-{flag}"\n'
        f'description = "Test API key for e2e"\n'
        f"disabled_in_toolcall_argument = false\n"
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


def test_secret_write_file_tmux_e2e():
    flag = _generate_flag()
    secret_value = f"sk-test-{flag}"

    secret_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_secret_"))
    config_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_config_"))
    _create_secret_config(secret_path, flag)
    _create_test_config(config_path, str(secret_path))

    test_file = Path(f"/tmp/test_secret_{os.getpid()}.txt")
    session_name = f"test_secret_{os.getpid()}"

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
                    f"the TEST_API_KEY secret value in the format: "
                    f"api_key = '<the secret value>'"
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
                if secret_value in content:
                    return

            last_output = _capture_tmux_output(session_name)

            if _tmux_pane_dead(session_name):
                break

            if not _tmux_session_exists(session_name):
                break

            time.sleep(POLL_INTERVAL)

        if test_file.exists() and secret_value in test_file.read_text():
            return

        pytest.fail(
            f"Secret write file test failed.\n"
            f"Secret value: {secret_value}\n"
            f"File exists: {test_file.exists()}\n"
            f"File content: {test_file.read_text() if test_file.exists() else 'N/A'}\n"
            f"Output:\n{last_output}"
        )
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
        config_path.unlink(missing_ok=True)
        secret_path.unlink(missing_ok=True)
        if test_file.exists():
            test_file.unlink()


def test_secret_masked_in_result_tmux_e2e():
    flag = _generate_flag()
    secret_value = f"sk-test-{flag}"

    secret_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_secret_"))
    config_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_config_"))
    _create_secret_config(secret_path, flag)
    _create_test_config(config_path, str(secret_path))

    test_file = Path(f"/tmp/test_secret_mask_{os.getpid()}.txt")
    test_file.write_text(f"api_key={secret_value}")

    session_name = f"test_secret_mask_{os.getpid()}"

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
                    f"Read the file at {test_file} and tell me its content. "
                    f"The file contains the TEST_API_KEY secret - "
                    f"make sure to protect it from being exposed."
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
            last_output = _capture_tmux_output(session_name)

            if secret_value in last_output:
                pytest.fail(
                    f"Secret value was NOT masked in TUI output!\n"
                    f"Secret value: {secret_value}\n"
                    f"Output:\n{last_output}"
                )

            if _tmux_pane_dead(session_name):
                break

            if not _tmux_session_exists(session_name):
                break

            time.sleep(POLL_INTERVAL)

        if secret_value not in last_output:
            return

        pytest.fail(
            f"Secret value was NOT masked in TUI output!\n"
            f"Secret value: {secret_value}\n"
            f"Output:\n{last_output}"
        )
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
        config_path.unlink(missing_ok=True)
        secret_path.unlink(missing_ok=True)
        if test_file.exists():
            test_file.unlink()
