import json
import sys
import subprocess
import os
import pty
import signal

import time
import base64
import select
import fcntl
import platform
import re
from pathlib import Path
from typing import TypedDict, NotRequired, Dict, Union


class TerminalDict(TypedDict):
    """终端信息字典类型"""

    master: int
    slave: int
    process: subprocess.Popen[bytes]
    columns: int
    lines: int
    last_read_pos: int


class TrojanSuccessResult(TypedDict):
    """Trojan方法成功返回结果类型"""

    message: str


class TrojanErrorResult(TypedDict):
    """Trojan方法错误返回结果类型"""

    error: str


TrojanResult = Union[TrojanSuccessResult, TrojanErrorResult]


class Trojan:
    def __init__(self):
        self.current_dir = os.getcwd()
        self.terminals: Dict[str, TerminalDict] = {}  # 终端实例字典

    def run_command(self, command, timeout=30):
        """执行命令"""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.current_dir,
            )
            output = f"返回码: {result.returncode}\n"
            if result.stdout:
                output += f"stdout:\n{result.stdout}\n"
            if result.stderr:
                output += f"stderr:\n{result.stderr}"
            return {"message": output}
        except subprocess.TimeoutExpired:
            return {"error": f"命令超时: {timeout}秒"}
        except Exception as e:
            return {"error": str(e)}

    def change_directory(self, directory):
        """改变当前目录"""
        try:
            os.chdir(directory)
            self.current_dir = os.getcwd()
            return {"message": f"已切换到目录: {self.current_dir}"}
        except Exception as e:
            return {"error": str(e)}

    def read_file(self, filepath, show_line_numbers=False):
        """读取文件"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if show_line_numbers:
                lines = content.splitlines()
                numbered = [f"{i+1}: {line}" for i, line in enumerate(lines)]
                content = "\n".join(numbered)

            return {"message": content}
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, filepath, content, override=False):
        """写入文件"""
        try:
            if os.path.exists(filepath) and not override:
                return {"error": f"文件已存在: {filepath}"}

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return {"message": f"文件已写入: {filepath}"}
        except Exception as e:
            return {"error": str(e)}

    def append_file(self, filepath, content, assume_empty_line=True):
        """追加文件"""
        try:
            if not os.path.exists(filepath):
                return {"error": f"文件不存在: {filepath}"}

            with open(filepath, "a", encoding="utf-8") as f:
                f.write(content)
            return {"message": f"内容已追加到: {filepath}"}
        except Exception as e:
            return {"error": str(e)}

    def replace_file_content(self, filepath, old, new, replace_times=None):
        """替换文件内容"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            if old not in content:
                return {"error": f"未找到内容: {old}"}

            if replace_times is None:
                if content.count(old) != 1:
                    return {"error": f"找到多次匹配: {content.count(old)}次"}
                new_content = content.replace(old, new, 1)
                count = 1
            elif replace_times > 0:
                new_content = content.replace(old, new, replace_times)
                count = replace_times
            elif replace_times == -1:
                new_content = content.replace(old, new)
                count = content.count(old)
            else:
                return {"error": f"无效的替换次数: {replace_times}"}

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)
            return {"message": f"已替换{count}次"}
        except Exception as e:
            return {"error": str(e)}

    def list_files(self, dirpath):
        """列出文件"""
        try:
            path = Path(dirpath)
            if not path.exists():
                return {"error": f"路径不存在: {dirpath}"}

            items = []
            for item in path.iterdir():
                items.append(
                    {
                        "name": item.name,
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else 0,
                    }
                )

            lines = []
            for item in items:
                dir_mark = "📁" if item["is_dir"] else "📄"
                size = f" ({item['size']}B)" if not item["is_dir"] else ""
                lines.append(f"{dir_mark} {item['name']}{size}")

            return {"message": "\n".join(lines)}
        except Exception as e:
            return {"error": str(e)}

    def get_absolute_path(self, path):
        """获取绝对路径"""
        try:
            abs_path = Path(path).absolute()
            return {"message": str(abs_path)}
        except Exception as e:
            return {"error": str(e)}

    def read_file_with_sed(self, expression, filepath):
        """执行sed表达式"""
        try:
            result = subprocess.run(
                ["sed", "-n", expression, filepath], capture_output=True, text=True
            )
            if result.returncode != 0:
                return {"error": result.stderr}
            return {"message": result.stdout}
        except Exception as e:
            return {"error": str(e)}

    def modify_file_with_sed(self, expression: str, filepath: str) -> dict:
        """使用sed修改文件

        Args:
            expression: sed表达式
            filepath: 文件路径

        Returns:
            包含message或error的字典
        """
        try:
            system = platform.system()
            if system == "Darwin":
                cmd = ["sed", "-i", "", expression, filepath]
            else:
                cmd = ["sed", "-i", expression, filepath]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return {"error": result.stderr}
            return {"message": "文件已修改"}
        except Exception as e:
            return {"error": str(e)}

    def insert_at_line(self, filepath, line_number, content, expected_line_content):
        """插入内容到指定行"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if line_number < 1 or line_number > len(lines) + 1:
                return {"error": f"行号无效: {line_number}"}

            if line_number <= len(lines):
                actual_line = lines[line_number - 1].rstrip("\n")
                if actual_line != expected_line_content:
                    return {
                        "error": f"行内容不匹配: 实际'{actual_line}', 预期'{expected_line_content}'"
                    }

            content_with_newline = content if content.endswith("\n") else content + "\n"
            lines.insert(line_number - 1, content_with_newline)

            with open(filepath, "w", encoding="utf-8") as f:
                f.writelines(lines)

            return {"message": f"已插入到第{line_number}行"}
        except Exception as e:
            return {"error": str(e)}

    def terminal_create(self, columns: int = 80, lines: int = 24) -> TrojanResult:
        """创建终端，返回终端ID

        Args:
            columns: 终端列数
            lines: 终端行数

        Returns:
            包含message的字典
        """
        # 确保fail-fast原则：立即验证参数有效性
        assert (
            columns > 0 and lines > 0
        ), f"终端尺寸必须大于0: columns={columns}, lines={lines}"

        term_id = f"term_{int(time.time()*1000)}_{len(self.terminals)}"
        master, slave = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm"
        env["COLUMNS"] = str(columns)
        env["LINES"] = str(lines)

        process = subprocess.Popen(
            ["/usr/bin/env", "bash", "-i"],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            start_new_session=True,
        )

        self.terminals[term_id] = {
            "master": master,
            "slave": slave,
            "process": process,
            "columns": columns,
            "lines": lines,
            "last_read_pos": 0,
        }

        # 设置为非阻塞模式以确保响应性
        fcntl.fcntl(master, fcntl.F_SETFL, os.O_NONBLOCK)

        return {"message": term_id}

    def terminal_send_keys(self, term_id: str, keys: list[str]) -> TrojanResult:
        """发送按键到终端

        Args:
            term_id: 终端ID
            keys: 按键名称列表

        Returns:
            包含message的字典
        """
        assert term_id in self.terminals, f"终端不存在: {term_id}"
        assert len(keys) > 0, "按键列表不能为空"

        terminal: TerminalDict = self.terminals[term_id]
        master = terminal["master"]

        key_mappings = {
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
            "ctrl+c": "\x03",
            "ctrl+d": "\x04",
            "ctrl+z": "\x1a",
        }

        for key in keys:
            if key in key_mappings:
                # 特殊按键需要映射到对应的控制序列
                os.write(master, key_mappings[key].encode())
            elif len(key) == 1:
                # 普通字符直接发送
                os.write(master, key.encode())
            else:
                raise AssertionError(f"未知按键: {key}")

        return {"message": f"已发送按键: {keys}"}

    def terminal_send_string(
        self, term_id: str, string: str, with_enter: bool = False
    ) -> TrojanResult:
        """发送字符串到终端

        Args:
            term_id: 终端ID
            string: 要发送的字符串
            with_enter: 是否发送回车键

        Returns:
            包含message的字典
        """
        assert term_id in self.terminals, f"终端不存在: {term_id}"
        assert len(string) > 0, "字符串不能为空"

        terminal: TerminalDict = self.terminals[term_id]
        master = terminal["master"]

        os.write(master, string.encode())
        if with_enter:
            # 发送回车键以模拟用户按下Enter
            os.write(master, b"\r")

        return {"message": f"已发送字符串: {string}"}

    def terminal_read_screen(self, term_id: str) -> TrojanResult:
        """读取终端屏幕内容，返回base64编码的原始字节流供pyte处理

        Args:
            term_id: 终端ID

        Returns:
            包含message的字典，message为base64编码的字节流
        """
        assert term_id in self.terminals, f"终端不存在: {term_id}"

        terminal: TerminalDict = self.terminals[term_id]
        master = terminal["master"]
        # 确保master是有效的文件描述符（非负整数）
        assert isinstance(master, int) and master >= 0, f"无效的文件描述符: {master}"

        # 读取可用的数据（非阻塞读取）
        data = b""
        while True:
            try:
                chunk = os.read(master, 1024)
                if not chunk:
                    break
                data += chunk
            except BlockingIOError:
                # 非阻塞模式下没有数据可读是正常情况
                break
            # 其他异常（如OSError）将直接传播，符合fail-fast原则

        # 返回base64编码的原始字节流，由pyte处理
        return {"message": base64.b64encode(data).decode("utf-8")}

    def terminal_close(self, term_id: str) -> TrojanResult:
        """关闭终端

        Args:
            term_id: 终端ID

        Returns:
            包含message的字典
        """
        assert term_id in self.terminals, f"终端不存在: {term_id}"

        terminal: TerminalDict = self.terminals[term_id]

        # 终止进程 - 遵循fail-fast原则，让异常传播
        os.killpg(os.getpgid(terminal["process"].pid), signal.SIGKILL)
        terminal["process"].wait(timeout=2)

        # 关闭文件描述符 - 遵循fail-fast原则，让异常传播
        os.close(terminal["master"])
        os.close(terminal["slave"])

        # 从字典中移除
        del self.terminals[term_id]

        return {"message": f"已关闭终端 {term_id}"}


def main():
    trojan = Trojan()

    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line.strip())
            method = request.get("method")
            params = request.get("params", {})

            if hasattr(trojan, method):
                result = getattr(trojan, method)(**params)
                response = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"message": f"方法未找到: {method}"},
                }

            print(json.dumps(response), flush=True)
        except Exception as e:
            request_id = None
            if request is not None:
                request_id = request.get("id")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"message": str(e)},
            }
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
