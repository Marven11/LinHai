"""终端控制工具模块，提供虚拟终端操作功能。"""

import asyncio
import os
import pty
import signal
import subprocess
from typing import List, Union

import pyte

from linhai.utils.common import generate_id
from .tmux_terminal import TmuxTerminal, is_tmux_available

terminals: dict[str, Union["PyteTerminal", TmuxTerminal]] = {}

_use_tmux = False


def configure_terminals(use_tmux: bool) -> None:
    global _use_tmux
    _use_tmux = use_tmux and is_tmux_available()


KEY_MAPPINGS = {
    "enter": "\r",
    "esc": "\x1b",
    "tab": "\t",
    "space": " ",
    "backspace": "\x7f",
    "up": "\x1b[A",
    "down": "\x1b[B",
    "left": "\x1b[D",
    "right": "\x1b[C",
    "home": "\x1b[H",
    "end": "\x1b[F",
    "insert": "\x1b[2~",
    "delete": "\x1b[3~",
    "pageup": "\x1b[5~",
    "pagedown": "\x1b[6~",
    "f1": "\x1bOP",
    "f2": "\x1bOQ",
    "f3": "\x1bOR",
    "f4": "\x1bOS",
    "f5": "\x1b[15~",
    "f6": "\x1b[17~",
    "f7": "\x1b[18~",
    "f8": "\x1b[19~",
    "f9": "\x1b[20~",
    "f10": "\x1b[21~",
    "f11": "\x1b[23~",
    "f12": "\x1b[24~",
    "ctrl+c": "\x03",
    "ctrl+d": "\x04",
    "ctrl+z": "\x1a",
    "ctrl+a": "\x01",
    "ctrl+e": "\x05",
    "ctrl+u": "\x15",
    "ctrl+k": "\x0b",
    "ctrl+l": "\x0c",
    "ctrl+r": "\x12",
}


class PyteTerminal:
    """基于pyte的虚拟终端类"""

    def __init__(
        self,
        columns: int = 80,
        lines: int = 24,
        bash_argv: list[str] | None = None,
    ):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream()
        self.stream.attach(self.screen)

        self.master, self.slave = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm"
        env["COLUMNS"] = str(columns)
        env["LINES"] = str(lines)

        if bash_argv is None:
            bash_argv = ["/usr/bin/env", "bash"]

        self.process = subprocess.Popen(
            bash_argv,
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            env=env,
            start_new_session=True,
        )

        self.loop = None
        self._stop_reading = False

    async def start_reading(self):
        """启动异步读取循环"""
        assert self.loop is None, "Reading loop already started"
        self._stop_reading = False
        self.loop = asyncio.get_running_loop()
        self.loop.add_reader(self.master, self._handle_read)

    def _handle_read(self):
        """处理读取事件"""
        data = os.read(self.master, 1024)
        if data:
            text = data.decode("utf-8", errors="ignore")
            self.stream.feed(text)

    def send(self, data: str | bytes):
        """发送数据到终端"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        os.write(self.master, data)

    def get_screen(self) -> str:
        """获取当前屏幕内容"""
        return "\n".join("".join(line) for line in self.screen.display)

    def send_key(self, key_name: str):
        """发送按键到终端"""
        if key_name not in KEY_MAPPINGS:
            raise ValueError(f"unknown key: {key_name}")
        key_data = KEY_MAPPINGS[key_name]
        self.send(key_data)

    def close(self):
        """关闭终端"""
        self._stop_reading = True
        if self.loop and self.master:
            self.loop.remove_reader(self.master)

        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process.wait(timeout=2)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            pass
        try:
            if self.process.poll() is None:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                self.process.wait()
        except OSError:
            pass
        try:
            os.close(self.master)
            os.close(self.slave)
        except OSError:
            pass


async def terminal_create(
    columns: int = 80,
    lines: int = 24,
    bash_argv: list[str] | None = None,
) -> str:
    """新建虚拟终端

    Args:
        columns: 终端列数
        lines: 终端行数
        bash_argv: bash启动命令的argv，为None时使用默认值

    Returns:
        终端对应的ID
    """
    try:
        term_id = generate_id("terminal")
        if _use_tmux:
            terminal = TmuxTerminal(columns=columns, lines=lines, bash_argv=bash_argv)
        else:
            terminal = PyteTerminal(columns=columns, lines=lines, bash_argv=bash_argv)
        terminals[term_id] = terminal
        await terminal.start_reading()
        return term_id
    except Exception as e:  # pylint: disable=broad-exception-caught
        return f"\u521b\u5efa\u7ec8\u7aef\u5931\u8d25: {e}"


def close_all_terminals() -> str:
    """关闭所有终端

    Returns:
        关闭结果消息
    """
    count = len(terminals)
    for terminal_id in list(terminals.keys()):
        terminal = terminals[terminal_id]
        terminal.close()
        del terminals[terminal_id]
    return f"\u5df2\u5173\u95ed\u6240\u6709\u7ec8\u7aef\uff0c\u5171{count}\u4e2a"


async def close_all_terminals_async() -> None:
    terminal_ids = list(terminals.keys())
    if not terminal_ids:
        return

    async def _close(tid: str) -> None:
        terminals[tid].close()
        del terminals[tid]

    await asyncio.gather(*[_close(tid) for tid in terminal_ids])


async def terminal_send_keys(terminal_id: str, keys: List[str]) -> str:
    """发送按键列表到终端

    Args:
        terminal_id: 终端ID
        keys: 按键名称列表

    Returns:
        执行结果消息
    """
    if terminal_id not in terminals:
        return f"\u9519\u8bef\uff1a\u672a\u627e\u5230\u7ec8\u7aef {terminal_id}"

    terminal = terminals[terminal_id]

    for key in keys:
        if key in KEY_MAPPINGS:
            terminal.send_key(key)
        elif len(key) == 1:
            terminal.send(key)
        else:
            return f"\u672a\u77e5\u6309\u952e: {key!r}, \u6240\u6709\u6309\u952e: {list(KEY_MAPPINGS.keys())}"

    return f"\u5df2\u53d1\u9001\u6309\u952e: {keys}"


async def terminal_send_string(
    terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
) -> str:
    if terminal_id not in terminals:
        return f"\u9519\u8bef\uff1a\u672a\u627e\u5230\u7ec8\u7aef {terminal_id}"

    terminal = terminals[terminal_id]
    terminal.send(string)
    if with_enter:
        terminal.send_key("enter")
    await asyncio.sleep(wait_seconds)
    content = terminal.get_screen()
    return f"\u5df2\u53d1\u9001: {string}, \u5f53\u524d\u5185\u5bb9:\n" + content


async def terminal_read_screen(terminal_id: str) -> str:
    """读取终端屏幕内容

    Args:
        terminal_id: 终端ID

    Returns:
        屏幕内容
    """
    if terminal_id not in terminals:
        return f"\u9519\u8bef\uff1a\u672a\u627e\u5230\u7ec8\u7aef {terminal_id}"

    terminal = terminals[terminal_id]
    return terminal.get_screen()


async def terminal_close(terminal_id: str) -> str:
    """关闭终端

    Args:
        terminal_id: 终端ID

    Returns:
        关闭结果消息
    """
    if terminal_id not in terminals:
        return f"\u9519\u8bef\uff1a\u672a\u627e\u5230\u7ec8\u7aef {terminal_id}"

    terminal = terminals[terminal_id]
    terminal.close()
    del terminals[terminal_id]
    return f"\u5df2\u5173\u95ed\u7ec8\u7aef {terminal_id}"
