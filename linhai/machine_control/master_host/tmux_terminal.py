import shutil
import subprocess
from collections.abc import Sequence

from linhai.utils.common import generate_id

KEY_TO_TMUX = {
    "enter": "Enter",
    "esc": "Escape",
    "tab": "Tab",
    "space": "Space",
    "backspace": "BSpace",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "home": "Home",
    "end": "End",
    "insert": "IC",
    "delete": "DC",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
    "ctrl+c": "C-c",
    "ctrl+d": "C-d",
    "ctrl+z": "C-z",
    "ctrl+a": "C-a",
    "ctrl+e": "C-e",
    "ctrl+u": "C-u",
    "ctrl+k": "C-k",
    "ctrl+l": "C-l",
    "ctrl+r": "C-r",
}

_SESSION_PREFIX = "linhai_"
_MAX_NAME_RETRIES = 3


def is_tmux_available() -> bool:
    return shutil.which("tmux") is not None


def _session_exists(name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", name],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


class TmuxTerminal:
    def __init__(
        self,
        columns: int = 80,
        lines: int = 24,
        shell_argv: Sequence[str] = ("/usr/bin/env", "bash"),
        cwd: str | None = None,
    ):
        self.session_name = _SESSION_PREFIX + generate_id("tmux")
        for _ in range(_MAX_NAME_RETRIES):
            if not _session_exists(self.session_name):
                break
            self.session_name = _SESSION_PREFIX + generate_id("tmux")
        else:
            raise ValueError(
                f"tmux session name conflict after {_MAX_NAME_RETRIES} retries: "
                f"{self.session_name}"
            )
        self._columns = columns
        self._lines = lines

        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                self.session_name,
                "-x",
                str(columns),
                "-y",
                str(lines),
                "-c",
                cwd or ".",
            ]
            + list(shell_argv),
            check=True,
            capture_output=True,
        )

    async def start_reading(self) -> None:
        pass

    def send(self, data: str) -> None:
        subprocess.run(
            ["tmux", "send-keys", "-t", self.session_name, "-l", data],
            check=True,
            capture_output=True,
        )

    def send_key(self, key_name: str) -> None:
        if key_name not in KEY_TO_TMUX:
            raise ValueError(f"unknown key: {key_name}")
        tmux_key = KEY_TO_TMUX[key_name]
        subprocess.run(
            ["tmux", "send-keys", "-t", self.session_name, tmux_key],
            check=True,
            capture_output=True,
        )

    def get_screen(self) -> str:
        result = subprocess.run(
            [
                "tmux",
                "capture-pane",
                "-t",
                self.session_name,
                "-p",
                "-J",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.split("\n")
        return "\n".join(lines[: self._lines])

    def close(self) -> None:
        subprocess.run(
            ["tmux", "kill-session", "-t", self.session_name],
            capture_output=True,
            check=False,
        )
