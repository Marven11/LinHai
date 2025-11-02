"""终端控制工具模块，提供虚拟终端操作功能。"""

import asyncio
import pyte
import pty
import os
import select
import uuid
import subprocess

from typing import List
from linhai.tool.base import ToolSet, ToolArgInfo

# 创建新的工具集，不注册到global tools
terminal_toolset = ToolSet()

# 存储终端实例的字典
terminals = {}

# 按键映射
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
}


class PyteTerminal:
    """基于pyte的虚拟终端类"""

    def __init__(self, columns: int = 80, lines: int = 24):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream()
        self.stream.attach(self.screen)

        self.master, self.slave = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "vt100"
        env["COLUMNS"] = str(columns)
        env["LINES"] = str(lines)

        self.process = subprocess.Popen(
            ["/usr/bin/env", "bash"],
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            env=env,
            # preexec_fn=os.setsid,  # Unsafe in threads
        )

    def send(self, data: str | bytes):
        """发送数据到终端"""
        if isinstance(data, str):
            data = data.encode("utf-8")
        os.write(self.master, data)

    def update(self):
        """更新屏幕状态"""
        while select.select([self.master], [], [], 0.1)[0]:
            try:
                data = os.read(self.master, 1024).decode("utf-8", errors="ignore")
                self.stream.feed(data)
            except (OSError, UnicodeDecodeError):
                break

    def get_screen(self) -> str:
        """获取当前屏幕内容"""
        return "\n".join("".join(line) for line in self.screen.display)

    def send_key(self, key_name: str):
        """发送按键到终端"""
        if key_name not in KEY_MAPPINGS:
            raise ValueError(f"未知按键: {key_name}")
        key_data = KEY_MAPPINGS[key_name]
        self.send(key_data)

    def close(self):
        """关闭终端"""
        try:
            os.close(self.master)
            os.close(self.slave)
        except OSError:
            pass


@terminal_toolset.register_tool(
    name="create_terminal",
    desc="新建虚拟终端，返回终端对应的uuid，需要等待并拿到UUID后才可操控终端",
    args={
        "columns": ToolArgInfo(desc="终端列数，默认80", type="int"),
        "lines": ToolArgInfo(desc="终端行数，默认24", type="int"),
    },
    required_args=[],
)
async def create_terminal(columns: int = 80, lines: int = 24) -> str:
    """新建虚拟终端

    Args:
        columns: 终端列数
        lines: 终端行数

    Returns:
        终端对应的uuid
    """
    term_uuid = str(uuid.uuid4())
    terminal = PyteTerminal(columns=columns, lines=lines)
    terminals[term_uuid] = terminal
    return term_uuid


@terminal_toolset.register_tool(
    name="send_keys_to_terminal",
    desc="发送按键列表到终端，特殊按键的定义和pyautogui相同，普通按键则传入对应字符，如'a'",
    args={
        "terminal_uuid": ToolArgInfo(desc="终端uuid", type="str"),
        "keys": ToolArgInfo(desc="按键名称列表", type="list"),
    },
    required_args=["terminal_uuid", "keys"],
)
async def send_keys_to_terminal(terminal_uuid: str, keys: List[str]) -> str:
    """发送按键列表到终端

    Args:
        terminal_uuid: 终端uuid
        keys: 按键名称列表

    Returns:
        执行结果消息
    """
    if terminal_uuid not in terminals:
        return f"错误：未找到终端 {terminal_uuid}"

    terminal = terminals[terminal_uuid]

    for key in keys:
        if key in KEY_MAPPINGS:
            terminal.send_key(key)
        elif len(key) == 1:
            terminal.send(key)
        else:
            return f"未知按键: {key!r}, 所有按键: {list(KEY_MAPPINGS.keys())}"

    terminal.update()
    return f"已发送按键: {keys}"


@terminal_toolset.register_tool(
    name="send_string_to_terminal",
    desc="发送命令等字符串到终端",
    args={
        "terminal_uuid": ToolArgInfo(desc="终端uuid", type="str"),
        "string": ToolArgInfo(desc="要发送的字符串", type="str"),
        "with_enter": ToolArgInfo(desc="是否发送enter，默认为True", type="bool"),
    },
    required_args=["terminal_uuid", "string"],
)
async def send_string_to_terminal(terminal_uuid: str, string: str, with_enter = True) -> str:
    """发送命令到终端

    Args:
        terminal_uuid: 终端uuid
        string: 要发送的命令

    Returns:
        执行结果消息
    """
    if terminal_uuid not in terminals:
        return f"错误：未找到终端 {terminal_uuid}"

    terminal = terminals[terminal_uuid]
    terminal.send(string)
    if with_enter:
        terminal.send_key("enter")
    terminal.update()
    await asyncio.sleep(0.1)
    terminal.update()
    content = terminal.get_screen()
    return f"已发送: {string}, 当前内容:\n" + content


@terminal_toolset.register_tool(
    name="read_terminal_screen",
    desc="读取当前终端的屏幕内容",
    args={"terminal_uuid": ToolArgInfo(desc="终端uuid", type="str")},
    required_args=["terminal_uuid"],
)
async def read_terminal_screen(terminal_uuid: str) -> str:
    """读取终端屏幕内容

    Args:
        terminal_uuid: 终端uuid

    Returns:
        屏幕内容
    """
    if terminal_uuid not in terminals:
        return f"错误：未找到终端 {terminal_uuid}"

    terminal = terminals[terminal_uuid]
    terminal.update()
    return terminal.get_screen()


@terminal_toolset.register_tool(
    name="close_terminal",
    desc="关闭终端",
    args={"terminal_uuid": ToolArgInfo(desc="终端uuid", type="str")},
    required_args=["terminal_uuid"],
)
async def close_terminal(terminal_uuid: str) -> str:
    """关闭终端

    Args:
        terminal_uuid: 终端uuid

    Returns:
        关闭结果消息
    """
    if terminal_uuid not in terminals:
        return f"错误：未找到终端 {terminal_uuid}"

    terminal = terminals[terminal_uuid]
    terminal.close()
    del terminals[terminal_uuid]
    return f"已关闭终端 {terminal_uuid}"


async def close_all_terminals() -> str:
    """关闭所有终端

    Returns:
        关闭结果消息
    """
    # global terminals  # No assignment done
    count = len(terminals)
    for terminal_uuid in list(terminals.keys()):
        terminal = terminals[terminal_uuid]
        terminal.close()
        del terminals[terminal_uuid]
    return f"已关闭所有终端，共{count}个"
