import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

BASE_URL = "http://192.168.114.149:8124/v1"
MODEL = "deepseek/deepseek-v4-flash"
TIMEOUT = 600
POLL_INTERVAL = 10


def _generate_uuid() -> str:
    return secrets.token_hex(16)


def _create_test_config(config_path: Path, secret_path: str) -> None:
    config_path.write_text(
        f"[[llm]]\n"
        f'name = "test-secret-custom"\n'
        f'base_url = "{BASE_URL}"\n'
        f'api_key = "gomodel-master-key"\n'
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


def _create_secret_config(secret_path: Path, secret_uuid: str) -> None:
    secret_path.write_text(
        f"[secrets]\n"
        f"[secrets.TEST_SECRET_UUID]\n"
        f'value = "{secret_uuid}"\n'
        f'description = "Test secret UUID for e2e"\n'
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


def test_secret_custom_toolcall_mask_and_read_e2e():
    secret_uuid = _generate_uuid()
    plaintext_uuid = _generate_uuid()

    secret_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_secret_custom_"))
    config_path = Path(tempfile.mktemp(suffix=".toml", prefix="test_config_custom_"))
    _create_secret_config(secret_path, secret_uuid)
    _create_test_config(config_path, str(secret_path))

    test_file = Path(f"/tmp/test_secret_custom_{os.getpid()}.txt")
    test_file.write_text(f"secret_id={secret_uuid}\nplain_id={plaintext_uuid}")

    session_name = f"test_secret_custom_{os.getpid()}"

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
                    f"Read the file at {test_file} using with_secret "
                    f"with TEST_SECRET_UUID in both in_arguments and in_result. "
                    f"Then tell me the value of plain_id in the file. "
                    f"Make sure the secret UUID is masked."
                ),
            ],
            check=True,
        )
        subprocess.run(
            ["tmux", "set-option", "-t", session_name, "remain-on-exit", "on"],
            check=False,
        )
        time.sleep(5)
        secret_path.unlink(missing_ok=True)

        start = time.time()
        last_output = ""
        while time.time() - start < TIMEOUT:
            last_output = _capture_tmux_output(session_name)

            if secret_uuid in last_output:
                pytest.fail(
                    f"Secret UUID was leaked in TUI output!\n"
                    f"Secret UUID: {secret_uuid}\n"
                    f"Plaintext UUID: {plaintext_uuid}\n"
                    f"Output:\n{last_output}"
                )

            if plaintext_uuid in last_output:
                return

            if _tmux_pane_dead(session_name):
                break

            if not _tmux_session_exists(session_name):
                break

            time.sleep(POLL_INTERVAL)

        if secret_uuid in last_output:
            pytest.fail(
                f"Secret UUID was leaked in TUI output!\n"
                f"Secret UUID: {secret_uuid}\n"
                f"Plaintext UUID: {plaintext_uuid}\n"
                f"Output:\n{last_output}"
            )

        if plaintext_uuid in last_output:
            return

        pytest.fail(
            f"Agent did not report the plaintext UUID.\n"
            f"Secret UUID: {secret_uuid}\n"
            f"Plaintext UUID: {plaintext_uuid}\n"
            f"Output:\n{last_output}"
        )
    finally:
        subprocess.run(["tmux", "kill-session", "-t", session_name], check=False)
        config_path.unlink(missing_ok=True)
        secret_path.unlink(missing_ok=True)
        if test_file.exists():
            test_file.unlink()
