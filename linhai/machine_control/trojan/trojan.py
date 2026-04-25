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
import tempfile
import shutil
import http.client
import urllib.parse
import ssl
from pathlib import Path
from typing import Any, TypedDict, Dict, Union, Set
from asyncio import Semaphore


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
        self.response_queue = asyncio.Queue()
        self.semaphore = Semaphore(32)
        self.active_tasks: Set[asyncio.Task] = set()

    async def ping(self):
        return {"message": "pong"}

    async def process_create(self, argv, wait_second=1.0):
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.current_dir,
            start_new_session=True,
        )
        pid = str(process.pid)
        self._processes[pid] = process

        elapsed = 0.0
        while elapsed < wait_second:
            await asyncio.sleep(0.1)
            elapsed += 0.1
            if process.returncode is not None:
                break

        if process.returncode is not None:
            stdout_data, stderr_data = b"", b""
            if process.stdout:
                stdout_data = await process.stdout.read()
            if process.stderr:
                stderr_data = await process.stderr.read()

            stdout_str = stdout_data.decode("utf-8", errors="replace")
            stderr_str = stderr_data.decode("utf-8", errors="replace")
            del self._processes[pid]
            return {
                "message": json.dumps(
                    {
                        "pid": pid,
                        "returncode": process.returncode,
                        "stdout": stdout_str,
                        "stderr": stderr_str,
                    }
                )
            }
        else:
            return {
                "message": json.dumps(
                    {
                        "pid": pid,
                        "message": f"等待失败，程序在{wait_second}秒后在运行。建议使用process_*系列工具进行读写stdio或者进一步等待程序",
                    }
                )
            }

    async def _read_process_stdio(
        self,
        process: asyncio.subprocess.Process,
        timeout: float = 2.0,
        max_read_size: int = 32 * 1024,
        check_exit: bool = False,
    ) -> tuple[str, str, str | None, str | None]:
        stdout_str, stderr_str = "", ""
        timeout_msg = ""
        exit_note = None

        if process.stdout:
            try:
                stdout_data = await asyncio.wait_for(
                    process.stdout.read(max_read_size), timeout=timeout
                )
                stdout_str = stdout_data.decode("utf-8", errors="replace")
            except asyncio.TimeoutError:
                timeout_msg += "读取stdout超时；"

        if process.stderr:
            try:
                stderr_data = await asyncio.wait_for(
                    process.stderr.read(max_read_size), timeout=timeout
                )
                stderr_str = stderr_data.decode("utf-8", errors="replace")
            except asyncio.TimeoutError:
                timeout_msg += "读取stderr超时；"

        if check_exit and process.returncode is not None:
            exit_note = f"注意：当前程序{process.pid}已经退出\n"

        if timeout_msg:
            timeout_msg = timeout_msg.rstrip("；")
        else:
            timeout_msg = None

        return stdout_str, stderr_str, timeout_msg, exit_note

    async def process_stdio_write(self, pid, content, with_enter=False):
        assert pid in self._processes, f"进程不存在: {pid}"
        process = self._processes[pid]
        assert process.stdin is not None, "进程没有stdin管道"
        if with_enter:
            content = content + "\n"
        process.stdin.write(content.encode())
        await process.stdin.drain()
        return {"message": f"已向进程 {pid} 写入 {len(content)} 字节"}

    async def process_stdio_read(self, pid, timeout=60.0):
        assert pid in self._processes, f"进程不存在: {pid}"
        process = self._processes[pid]
        stdout_str, stderr_str, timeout_msg, exit_note = await self._read_process_stdio(
            process, timeout=timeout, max_read_size=32 * 1024, check_exit=True
        )

        result_data = {
            "pid": pid,
            "stdout": stdout_str,
            "stderr": stderr_str,
        }

        if exit_note:
            result_data["exit_note"] = exit_note

        return {"message": json.dumps(result_data)}

    async def process_wait(self, pid, timeout):
        assert pid in self._processes, f"进程不存在: {pid}"
        process = self._processes[pid]
        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"message": json.dumps({"pid": pid, "timeout": True})}
        stdout_data, stderr_data = b"", b""
        if process.stdout:
            stdout_data = await process.stdout.read()
        if process.stderr:
            stderr_data = await process.stderr.read()
        stdout_str = stdout_data.decode("utf-8", errors="replace")
        stderr_str = stderr_data.decode("utf-8", errors="replace")
        del self._processes[pid]
        return {
            "message": json.dumps(
                {
                    "pid": pid,
                    "returncode": process.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                }
            )
        }

    async def process_kill(self, pid, graceful=True):
        assert pid in self._processes, f"进程不存在: {pid}"
        process = self._processes[pid]
        if graceful:
            process.terminate()
        else:
            process.kill()
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            return {"error": f"杀死进程 {pid} 超时"}
        del self._processes[pid]
        return {"message": f"进程 {pid} 已被杀死"}

    async def change_directory(self, directory):
        os.chdir(directory)
        self.current_dir = os.getcwd()
        return {"message": f"已切换到目录: {self.current_dir}"}

    async def read_file(self, filepath, show_line_numbers=False):
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

    async def write_file(self, filepath, content, override=False):
        if os.path.exists(filepath) and not override:
            return {"error": f"文件已存在: {filepath}"}
        Path(filepath).write_text(content, encoding="utf-8")
        return {"message": f"文件已写入: {filepath}"}

    async def replace_file_content(self, filepath, old, new, replace_times=None):
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

    async def list_files(self, dirpath, glob=False):
        if glob:
            return {"error": "glob仅支持master_host"}
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

    async def get_absolute_path(self, path):
        abs_path = Path(path).absolute()
        return {"message": str(abs_path)}

    async def read_file_with_sed(self, expression, filepath):
        process = await asyncio.create_subprocess_exec(
            "sed",
            "-n",
            expression,
            filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            return {"error": stderr.decode()}
        return {"message": stdout.decode()}

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
            "/usr/bin/env",
            "sh",
            "-i",
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
        self,
        term_id: str,
        string: str,
        with_enter: bool = False,
        wait_seconds: float = 0.3,
    ) -> TrojanResult:
        assert term_id in self.terminals, f"终端不存在: {term_id}"
        assert len(string) > 0, "字符串不能为空"

        terminal: TerminalDict = self.terminals[term_id]
        master = terminal["master"]

        os.write(master, string.encode())
        if with_enter:
            os.write(master, b"\r")

        await asyncio.sleep(wait_seconds)

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

    async def terminal_list(self) -> TrojanResult:
        if not self.terminals:
            return {"message": "<<terminals>>没有活动的终端<<terminals>>"}

        lines = []
        for term_id, terminal in self.terminals.items():
            try:
                term_info = {
                    "terminal_id": term_id,
                    "machine": "remote",
                    "screen": "终端屏幕内容（需通过read_screen获取）",
                    "columns": terminal["columns"],
                    "lines": terminal["lines"],
                }
                lines.append(
                    f"<<terminal_id>>{term_id}<<terminal_id>><<machine>>remote<<machine>><<columns>>{term_info['columns']}<<columns>><<lines>>{term_info['lines']}<<lines>>"
                )
            except Exception:
                lines.append(
                    f"<<terminal_id>>{term_id}<<terminal_id>><<machine>>remote<<machine>><<screen>>无法获取终端信息<<screen>>"
                )
        return {"message": "\n".join(lines)}

    async def get_file_size(self, filepath: str) -> TrojanResult:
        size = os.path.getsize(filepath)
        return {"message": str(size)}

    async def upload_chunk(self, chunk_data_base64: str, filepath: str) -> TrojanResult:
        chunk_data = base64.b64decode(chunk_data_base64)
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(chunk_data)
        return {"message": f"块已写入: {filepath}"}

    async def download_chunk(
        self, filepath: str, offset: int, length: int
    ) -> TrojanResult:
        with open(filepath, "rb") as f:
            f.seek(offset)
            chunk_data = f.read(length)
            if not chunk_data:
                return {
                    "error": f"偏移量超出文件范围: offset={offset}, length={length}"
                }
            chunk_base64 = base64.b64encode(chunk_data).decode("utf-8")
            return {"message": chunk_base64}

    async def concatenate_files(
        self, filepaths: list[str], output_path: str
    ) -> TrojanResult:
        with open(output_path, "wb") as outfile:
            for filepath in filepaths:
                if not os.path.exists(filepath):
                    return {"error": f"文件不存在: {filepath}"}
                with open(filepath, "rb") as infile:
                    while True:
                        chunk = infile.read(8192)
                        if not chunk:
                            break
                        outfile.write(chunk)
        return {"message": f"文件已拼接: {output_path}"}

    async def create_temp_dir(self, prefix: str = "temp") -> TrojanResult:
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        return {"message": temp_dir}

    async def remove_path(self, path: str) -> TrojanResult:
        if os.path.isfile(path) or os.path.islink(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            return {"error": f"路径不存在: {path}"}
        return {"message": f"已删除: {path}"}

    async def http_request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
        data: str | None = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: list[str] | None = None,
        cookies: dict | None = None,
        json_data: dict | None = None,
        proxy: str | None = None,
        verify: bool | None = None,
    ):
        if params:
            query = urllib.parse.urlencode(params)
            parsed = urllib.parse.urlparse(url)
            new_query = f"{parsed.query}&{query}" if parsed.query else query
            url = urllib.parse.urlunparse(parsed._replace(query=new_query))

        req_headers: dict[str, str] = dict(headers) if headers else {}
        req_headers.setdefault(
            "User-Agent", "Mozilla/5.0 (compatible; LinHai/1.0; Chrome-like)"
        )

        if json_data is not None:
            body: bytes | None = json.dumps(json_data).encode()
            req_headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            body = data.encode() if isinstance(data, str) else data
        else:
            body = None

        if auth:
            cred = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            req_headers["Authorization"] = f"Basic {cred}"

        if cookies:
            req_headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

        ctx = ssl.create_default_context()
        if verify is False:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        max_redirects = 10 if follow_redirects else 0

        def _do_request():
            redirects_left = max_redirects
            current = url
            cur_method = method.upper()
            cur_body = body

            while True:
                p = urllib.parse.urlparse(current)
                host = p.hostname or "localhost"
                port = p.port

                if proxy:
                    pp = urllib.parse.urlparse(
                        "//" + proxy if "://" not in proxy else proxy
                    )
                    p_host = pp.hostname or "localhost"
                    p_port = pp.port or 8080
                    if p.scheme == "https":
                        conn = http.client.HTTPSConnection(
                            p_host, p_port, context=ctx, timeout=timeout
                        )
                        conn.set_tunnel(host, port)
                    else:
                        conn = http.client.HTTPConnection(
                            p_host, p_port, timeout=timeout
                        )
                elif p.scheme == "https":
                    conn = http.client.HTTPSConnection(
                        host, port, context=ctx, timeout=timeout
                    )
                else:
                    conn = http.client.HTTPConnection(host, port, timeout=timeout)

                req_path = p.path or "/"
                if p.query:
                    req_path = f"{req_path}?{p.query}"

                conn.request(cur_method, req_path, body=cur_body, headers=req_headers)
                response = conn.getresponse()
                content = response.read()
                status = response.status
                resp_hdrs = dict(response.getheaders())
                ct = response.getheader("Content-Type", "")
                conn.close()

                if not follow_redirects or status not in (301, 302, 303, 307, 308):
                    return status, resp_hdrs, content, ct

                if redirects_left <= 0:
                    return status, resp_hdrs, content, ct

                redirects_left -= 1
                location = response.getheader("Location", "")
                if not location:
                    return status, resp_hdrs, content, ct

                current = urllib.parse.urljoin(current, location)
                if status == 303:
                    cur_method = "GET"
                    cur_body = None

        status_code, resp_headers, content, content_type = await asyncio.to_thread(
            _do_request
        )

        return {
            "message": json.dumps(
                {
                    "status_code": status_code,
                    "headers": resp_headers,
                    "content_base64": base64.b64encode(content).decode(),
                    "content_type": content_type.lower() if content_type else "",
                }
            )
        }

    def _remove_task(self, t):
        self.active_tasks.remove(t)

    async def _handle_request(self, method, params, request_id):
        async with self.semaphore:
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
            await self.response_queue.put(response)

    async def process_requests(self):
        while True:
            request = await self.request_queue.get()
            if request is None:
                for task in self.active_tasks:
                    task.cancel()
                if self.active_tasks:
                    await asyncio.gather(*self.active_tasks, return_exceptions=True)
                await self.response_queue.put(None)
                break
            request_data, request_id = request
            method = request_data.get("method")
            params = request_data.get("params", {})
            task = asyncio.get_running_loop().create_task(
                self._handle_request(method, params, request_id)
            )
            self.active_tasks.add(task)
            task.add_done_callback(self._remove_task)

    def _set_marker(self, marker_hex: str) -> None:
        self._marker_open = f"<linhai_trojanpy_{marker_hex}>"
        self._marker_close = f"</linhai_trojanpy_{marker_hex}>"

    async def read_input(self):
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        buf = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                await self.request_queue.put(None)
                break
            buf += chunk
            while True:
                start_idx = buf.find(self._marker_open.encode())
                if start_idx == -1:
                    if len(buf) > len(self._marker_open):
                        buf = buf[-len(self._marker_open) :]
                    break
                close_idx = buf.find(self._marker_close.encode(), start_idx)
                if close_idx == -1:
                    if len(buf) - start_idx > 1024 * 1024:
                        buf = buf[start_idx:]
                    break
                json_start = start_idx + len(self._marker_open)
                json_bytes = buf[json_start:close_idx]
                buf = buf[close_idx + len(self._marker_close) :]
                request = json.loads(json_bytes.decode("utf-8", errors="replace"))
                request_id = request.get("id")
                await self.request_queue.put((request, request_id))

    async def write_responses(self):
        while True:
            response = await self.response_queue.get()
            if response is None:
                break
            async with self.stdout_lock:
                data = f"{self._marker_open}{json.dumps(response)}{self._marker_close}"
                sys.stdout.write(data)
                sys.stdout.flush()


def main():
    marker_hex = sys.argv[1] if len(sys.argv) > 1 else None
    if not marker_hex:
        print("Usage: trojan.py <4-hex-marker>", file=sys.stderr)
        sys.exit(1)

    trojan = Trojan()
    trojan._set_marker(marker_hex)

    async def _run():
        loop = asyncio.get_running_loop()
        reader_task = loop.create_task(trojan.read_input())
        processor_task = loop.create_task(trojan.process_requests())
        writer_task = loop.create_task(trojan.write_responses())
        await asyncio.gather(
            reader_task, processor_task, writer_task, return_exceptions=True
        )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
