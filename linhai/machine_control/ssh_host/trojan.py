import json
import sys
import subprocess
import os
import pty
import signal
import time
import base64
import fcntl
import platform
import asyncio
from pathlib import Path
from typing import TypedDict, Dict, Union


class TerminalDict(TypedDict):
    master: int
    slave: int
    process: asyncio.subprocess.Process
    columns: int
    lines: int
    last_read_pos: int


class TrojanSuccessResult(TypedDict):
    message: str


class TrojanErrorResult(TypedDict):
    error: str


TrojanResult = Union[TrojanSuccessResult, TrojanErrorResult]


class Trojan:
    def __init__(self):
        self.current_dir = os.getcwd()
        self.terminals: Dict[str, TerminalDict] = {}
        self._processes: Dict[str, asyncio.subprocess.Process] = {}
        self.stdout_lock = asyncio.Lock()
        self.request_queue = asyncio.Queue()

    async def process_create(self, command, wait_second=1.0):
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.current_dir,
            )
            pid = str(process.pid)
            self._processes[pid] = process

            elapsed = 0.0
            while elapsed < wait_second:
                await asyncio.sleep(0.1)
                elapsed += 0.1
                if process.returncode is not None:
                    break

            stdout_data, stderr_data = b"", b""
            if process.stdout:
                stdout_data = await process.stdout.read()
            if process.stderr:
                stderr_data = await process.stderr.read()

            stdout_str = stdout_data.decode("utf-8", errors="replace")
            stderr_str = stderr_data.decode("utf-8", errors="replace")

            if process.returncode is not None:
                del self._processes[pid]
                return {
                    "message": json.dumps({
                        "pid": pid,
                        "returncode": process.returncode,
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                    })
                }
            else:
                return {
                    "message": json.dumps({
                        "pid": pid,
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                        "message": "程序仍然在运行",
                    })
                }
        except Exception as e:
            return {"error": str(e)}

    async def change_directory(self, directory):
        try:
            os.chdir(directory)
            self.current_dir = os.getcwd()
            return {"message": f"已切换到目录: {self.current_dir}"}
        except Exception as e:
            return {"error": str(e)}

    async def read_file(self, filepath, show_line_numbers=False):
        try:
            with open(filepath, "rb") as f:
                content = bytearray()
                while True:
                    chunk = f.read(128 * 1024)
                    if not chunk:
                        break
                    content.extend(chunk)
                    await asyncio.sleep(0)
            text_content = content.decode("utf-8")
            if show_line_numbers:
                lines = text_content.splitlines()
                numbered = [f"{i+1}: {line}" for i, line in enumerate(lines)]
                text_content = "\n".join(numbered)
            return {"message": text_content}
        except Exception as e:
            return {"error": str(e)}

    async def write_file(self, filepath, content, override=False):
        try:
            if os.path.exists(filepath) and not override:
                return {"error": f"文件已存在: {filepath}"}
            Path(filepath).write_text(content, encoding="utf-8")
            return {"message": f"文件已写入: {filepath}"}
        except Exception as e:
            return {"error": str(e)}

    async def replace_file_content(self, filepath, old, new, replace_times=None):
        try:
            content = Path(filepath).read_text(encoding="utf-8")
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
            Path(filepath).write_text(new_content, encoding="utf-8")
            return {"message": f"已替换{count}次"}
        except Exception as e:
            return {"error": str(e)}

    async def list_files(self, dirpath):
        try:
            path = Path(dirpath)
            if not path.exists():
                return {"error": f"路径不存在: {dirpath}"}
            items = []
            for item in path.iterdir():
                is_dir = item.is_dir()
                size = item.stat().st_size if not is_dir else 0
                items.append({"name": item.name, "is_dir": is_dir, "size": size})
            lines = []
            for item in items:
                dir_mark = "📁" if item["is_dir"] else "📄"
                size = f" ({item['size']}B)" if not item["is_dir"] else ""
                lines.append(f"{dir_mark} {item['name']}{size}")
            return {"message": "\n".join(lines)}
        except Exception as e:
            return {"error": str(e)}

    async def get_absolute_path(self, path):
        try:
            abs_path = Path(path).absolute()
            return {"message": str(abs_path)}
        except Exception as e:
            return {"error": str(e)}

    async def read_file_with_sed(self, expression, filepath):
        try:
            process = await asyncio.create_subprocess_exec(
                "sed", "-n", expression, filepath,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                return {"error": stderr.decode()}
            return {"message": stdout.decode()}
        except Exception as e:
            return {"error": str(e)}

    async def modify_file_with_sed(self, expression: str, filepath: str) -> dict:
        try:
            system = platform.system()
            if system == "Darwin":
                cmd = ["sed", "-i", "", expression, filepath]
            else:
                cmd = ["sed", "-i", expression, filepath]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                return {"error": stderr.decode()}
            return {"message": "文件已修改"}
        except Exception as e:
            return {"error": str(e)}

    async def insert_at_line(self, filepath, line_number, content, expected_line_content):
        try:
            lines = Path(filepath).read_text(encoding="utf-8").splitlines(keepends=True)
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
            Path(filepath).write_text(''.join(lines), encoding="utf-8")
            return {"message": f"已插入到第{line_number}行"}
        except Exception as e:
            return {"error": str(e)}

    async def terminal_create(self, columns: int = 80, lines: int = 24) -> TrojanResult:
        assert (
            columns > 0 and lines > 0
        ), f"终端尺寸必须大于0: columns={columns}, lines={lines}"

        term_id = f"term_{int(time.time()*1000)}_{len(self.terminals)}"
        master, slave = pty.openpty()

        env = os.environ.copy()
        env["TERM"] = "xterm"
        env["COLUMNS"] = str(columns)
        env["LINES"] = str(lines)

        process = await asyncio.create_subprocess_exec(
            "/usr/bin/env", "bash", "-i",
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=env,
            preexec_fn=os.setsid,
        )

        self.terminals[term_id] = {
            "master": master,
            "slave": slave,
            "process": process,
            "columns": columns,
            "lines": lines,
            "last_read_pos": 0,
        }

        fcntl.fcntl(master, fcntl.F_SETFL, os.O_NONBLOCK)

        return {"message": term_id}

    async def terminal_send_keys(self, term_id: str, keys: list[str]) -> TrojanResult:
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
                os.write(master, key_mappings[key].encode())
            elif len(key) == 1:
                os.write(master, key.encode())
            else:
                raise AssertionError(f"未知按键: {key}")

        return {"message": f"已发送按键: {keys}"}

    async def terminal_send_string(
        self, term_id: str, string: str, with_enter: bool = False
    ) -> TrojanResult:
        assert term_id in self.terminals, f"终端不存在: {term_id}"
        assert len(string) > 0, "字符串不能为空"

        terminal: TerminalDict = self.terminals[term_id]
        master = terminal["master"]

        os.write(master, string.encode())
        if with_enter:
            os.write(master, b"\r")

        return {"message": f"已发送字符串: {string}"}

    async def terminal_read_screen(self, term_id: str) -> TrojanResult:
        assert term_id in self.terminals, f"终端不存在: {term_id}"

        terminal: TerminalDict = self.terminals[term_id]
        master = terminal["master"]
        assert isinstance(master, int) and master >= 0, f"无效的文件描述符: {master}"

        data = b""
        while True:
            try:
                chunk = os.read(master, 1024)
                if not chunk:
                    break
                data += chunk
            except BlockingIOError:
                break

        return {"message": base64.b64encode(data).decode("utf-8")}

    async def terminal_close(self, term_id: str) -> TrojanResult:
        assert term_id in self.terminals, f"终端不存在: {term_id}"

        terminal: TerminalDict = self.terminals[term_id]
        process = terminal["process"]
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
        os.close(terminal["master"])
        os.close(terminal["slave"])
        del self.terminals[term_id]
        return {"message": f"已关闭终端 {term_id}"}

    async def process_requests(self):
        while True:
            request = await self.request_queue.get()
            if request is None:
                break
            request_data, request_id = request
            method = request_data.get("method")
            params = request_data.get("params", {})

            try:
                if hasattr(self, method):
                    result = await getattr(self, method)(**params)
                    response = {"jsonrpc": "2.0", "id": request_id, "result": result}
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"message": f"方法未找到: {method}"},
                    }
            except Exception as e:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"message": str(e)},
                }

            async with self.stdout_lock:
                print(json.dumps(response), flush=True)

    async def read_input(self):
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        
        while True:
            line = await reader.readline()
            if not line:
                break
            line = line.decode().strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                request_id = request.get("id")
                await self.request_queue.put((request, request_id))
            except Exception:
                pass


async def main():
    trojan = Trojan()
    reader_task = asyncio.create_task(trojan.read_input())
    processor_task = asyncio.create_task(trojan.process_requests())
    await asyncio.gather(reader_task, processor_task)


if __name__ == "__main__":
    asyncio.run(main())
