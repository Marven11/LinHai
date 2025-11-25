"""终端控制工具模块，提供虚拟终端操作功能。"""

import time
import pyte
import pty
import os
import select
import signal
import subprocess

from typing import List
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.utils import generate_id

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

    def __init__(self, columns: int = 80, lines: int = 24):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream()
        self.stream.attach(self.screen)

        self.master, self.slave = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm"
        env["COLUMNS"] = str(columns)
        env["LINES"] = str(lines)

        self.process = subprocess.Popen(
            ["/usr/bin/env", "bash"],
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            env=env,
            start_new_session=True,
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
            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
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


@terminal_toolset.register_tool(
    name="create_terminal",
    desc="新建虚拟终端，返回终端对应的ID，这个工具不能和其他工具一起调用！",
    args={
        "columns": ToolArgInfo(desc="终端列数，默认80", type="int"),
        "lines": ToolArgInfo(desc="终端行数，默认24", type="int"),
    },
    required_args=[],
    conflict_with=[
        "send_keys_to_terminal",
        "send_string_to_terminal",
        "read_terminal_screen",
    ],
)
def create_terminal(columns: int = 80, lines: int = 24) -> str:
    """新建虚拟终端

    Args:
        columns: 终端列数
        lines: 终端行数

    Returns:
        终端对应的ID
    """
    term_id = generate_id("terminal")
    terminal = PyteTerminal(columns=columns, lines=lines)
    terminals[term_id] = terminal
    return term_id


@terminal_toolset.register_tool(
    name="send_keys_to_terminal",
    desc="发送按键列表到终端，特殊按键的定义和pyautogui相同，普通按键则传入对应字符，如'a'。如果需要发送ctrl+c等控制字符，请传入对应的控制键名称，如'ctrl+c'、'ctrl+d'等。",
    args={
        "terminal_id": ToolArgInfo(desc="终端ID", type="str"),
        "keys": ToolArgInfo(
            desc="""按键名称列表，如["esc", ":", "q", "enter"]""", type="list"
        ),
    },
    required_args=["terminal_id", "keys"],
)
def send_keys_to_terminal(terminal_id: str, keys: List[str]) -> str:
    """发送按键列表到终端

    Args:
        terminal_id: 终端ID
        keys: 按键名称列表

    Returns:
        执行结果消息
    """
    if terminal_id not in terminals:
        return f"错误：未找到终端 {terminal_id}"

    terminal = terminals[terminal_id]

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
        "terminal_id": ToolArgInfo(desc="终端ID", type="str"),
        "string": ToolArgInfo(desc="要发送的字符串", type="str"),
        "wait_seconds": ToolArgInfo(
            desc="等待一段时间后读取最新画面，默认等待0.3秒", type="float"
        ),
        "with_enter": ToolArgInfo(desc="是否发送enter，默认为True", type="bool"),
    },
    required_args=["terminal_id", "string"],
)
def send_string_to_terminal(
    terminal_id: str, string: str, wait_seconds: float = 0.3, with_enter=True
) -> str:
    if terminal_id not in terminals:
        return f"错误：未找到终端 {terminal_id}"

    terminal = terminals[terminal_id]
    terminal.send(string)
    if with_enter:
        terminal.send_key("enter")
    terminal.update()
    time.sleep(wait_seconds)
    terminal.update()
    content = terminal.get_screen()
    return f"已发送: {string}, 当前内容:\n" + content


@terminal_toolset.register_tool(
    name="read_terminal_screen",
    desc="读取当前终端的屏幕内容",
    args={"terminal_id": ToolArgInfo(desc="终端ID", type="str")},
    required_args=["terminal_id"],
)
def read_terminal_screen(terminal_id: str) -> str:
    """读取终端屏幕内容

    Args:
        terminal_id: 终端ID

    Returns:
        屏幕内容
    """
    if terminal_id not in terminals:
        return f"错误：未找到终端 {terminal_id}"

    terminal = terminals[terminal_id]
    terminal.update()
    return terminal.get_screen()


@terminal_toolset.register_tool(
    name="close_terminal",
    desc="关闭终端",
    args={"terminal_id": ToolArgInfo(desc="终端ID", type="str")},
    required_args=["terminal_id"],
)
def close_terminal(terminal_id: str) -> str:
    """关闭终端

    Args:
        terminal_id: 终端ID

    Returns:
        关闭结果消息
    """
    if terminal_id not in terminals:
        return f"错误：未找到终端 {terminal_id}"

    terminal = terminals[terminal_id]
    terminal.close()
    del terminals[terminal_id]
    return f"已关闭终端 {terminal_id}"


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
    return f"已关闭所有终端，共{count}个"
