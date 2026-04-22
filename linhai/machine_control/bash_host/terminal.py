from __future__ import annotations

import asyncio
import shlex
from typing import TYPE_CHECKING

from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.utils.common import generate_id

if TYPE_CHECKING:
    from .bash_host import BashHostControl

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

_terminals: dict[str, dict[str, str]] = {}


def _make_session_name() -> str:
    return _SESSION_PREFIX + generate_id("tmux")


async def check_tmux_available(host: BashHostControl) -> bool:
    rc, _, _ = await host.execute_raw("command -v tmux >/dev/null 2>&1")
    return rc == 0


async def terminal_create(
    host: BashHostControl,
    columns: int = 80,
    lines: int = 24,
) -> ToolResultSuccess | ToolResultFailed:
    if not await check_tmux_available(host):
        return ToolResultFailed(content="远程机器没有安装tmux，无法创建终端")

    session_name = _make_session_name()
    cmd = (
        f"tmux new-session -d -s {shlex.quote(session_name)}"
        f" -x {columns} -y {lines}"
    )
    rc, stdout, stderr = await host.execute_raw(cmd)
    if rc != 0:
        return ToolResultFailed(content=f"创建终端失败: {stderr or stdout}")

    term_id = generate_id("terminal")
    _terminals[term_id] = {
        "session_name": session_name,
        "columns": str(columns),
        "lines": str(lines),
    }
    return ToolResultSuccess(content=term_id)


async def terminal_send_keys(
    host: BashHostControl,
    terminal_id: str,
    keys: list[str],
) -> ToolResultSuccess | ToolResultFailed:
    if terminal_id not in _terminals:
        return ToolResultFailed(content=f"未找到终端 {terminal_id}")

    session = _terminals[terminal_id]["session_name"]
    for key in keys:
        if key in KEY_TO_TMUX:
            tmux_key = KEY_TO_TMUX[key]
            cmd = f"tmux send-keys -t {shlex.quote(session)} {shlex.quote(tmux_key)}"
        elif len(key) == 1:
            cmd = f"tmux send-keys -t {shlex.quote(session)} -l {shlex.quote(key)}"
        else:
            return ToolResultFailed(
                content=f"未知按键: {key!r}, 所有按键: {list(KEY_TO_TMUX.keys())}"
            )
        rc, _, stderr = await host.execute_raw(cmd)
        if rc != 0:
            return ToolResultFailed(content=f"发送按键失败: {stderr}")

    return ToolResultSuccess(content=f"已发送按键: {keys}")


async def terminal_send_string(
    host: BashHostControl,
    terminal_id: str,
    string: str,
    with_enter: bool,
    wait_seconds: float = 0.3,
) -> ToolResultSuccess | ToolResultFailed:
    if terminal_id not in _terminals:
        return ToolResultFailed(content=f"未找到终端 {terminal_id}")

    session = _terminals[terminal_id]["session_name"]
    cmd = f"tmux send-keys -t {shlex.quote(session)} -l {shlex.quote(string)}"
    rc, _, stderr = await host.execute_raw(cmd)
    if rc != 0:
        return ToolResultFailed(content=f"发送字符串失败: {stderr}")

    if with_enter:
        cmd = f"tmux send-keys -t {shlex.quote(session)} Enter"
        rc, _, stderr = await host.execute_raw(cmd)
        if rc != 0:
            return ToolResultFailed(content=f"发送回车失败: {stderr}")

    await asyncio.sleep(wait_seconds)
    screen = await terminal_read_screen(host, terminal_id)
    if isinstance(screen, ToolResultFailed):
        return screen
    return ToolResultSuccess(content=f"已发送: {string}, 当前内容:\n" + screen.content)


async def terminal_read_screen(
    host: BashHostControl,
    terminal_id: str,
) -> ToolResultSuccess | ToolResultFailed:
    if terminal_id not in _terminals:
        return ToolResultFailed(content=f"未找到终端 {terminal_id}")

    session = _terminals[terminal_id]["session_name"]
    lines_count = int(_terminals[terminal_id]["lines"])
    cmd = f"tmux capture-pane -t {shlex.quote(session)} -p -J"
    rc, stdout, stderr = await host.execute_raw(cmd)
    if rc != 0:
        return ToolResultFailed(content=f"读取屏幕失败: {stderr}")

    lines = stdout.split("\n")
    content = "\n".join(lines[:lines_count])
    return ToolResultSuccess(content=content)


async def terminal_close(
    host: BashHostControl,
    terminal_id: str,
) -> ToolResultSuccess | ToolResultFailed:
    if terminal_id not in _terminals:
        return ToolResultFailed(content=f"未找到终端 {terminal_id}")

    session = _terminals[terminal_id]["session_name"]
    cmd = f"tmux kill-session -t {shlex.quote(session)}"
    await host.execute_raw(cmd)
    del _terminals[terminal_id]
    return ToolResultSuccess(content=f"已关闭终端 {terminal_id}")


async def get_terminals(
    host: BashHostControl,
    machine_id: str,
) -> ToolResultSuccess | ToolResultFailed:
    if not _terminals:
        return ToolResultSuccess(content="<<terminals>>没有活动的终端<<terminals>>")

    lines = []
    for term_id in _terminals:
        screen_result = await terminal_read_screen(host, term_id)
        screen = (
            screen_result.content
            if isinstance(screen_result, ToolResultSuccess)
            else "无法获取屏幕内容"
        )
        lines.append(
            f"<<terminal_id>>{term_id}<<terminal_id>><<machine>>{machine_id}<<machine>><<screen>>{screen}<<screen>>"
        )
    return ToolResultSuccess(content="\n".join(lines))
