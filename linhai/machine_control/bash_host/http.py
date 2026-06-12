from __future__ import annotations

import base64
import json
import shlex
from typing import TYPE_CHECKING, Any, Optional, Union
from urllib.parse import urlencode

from linhai.machine_control.http_message import HttpToolResult, build_http_message
from linhai.tool.base import FailedToolResult

if TYPE_CHECKING:
    from .bash_host import BashHostControl

_WRITEOUT_PREFIX = "__LINHAI_HTTP_R__"


async def http_request(
    host: BashHostControl,
    method: str,
    url: str,
    params: Optional[dict[str, Union[str, int, float, bool]]] = None,
    headers: Optional[dict[str, str]] = None,
    data: Optional[str] = None,
    follow_redirects: bool = False,
    timeout: int = 60,
    auth: Optional[tuple[str, str]] = None,
    cookies: Optional[dict[str, str]] = None,
    json_data: Optional[dict[str, Any]] = None,
    proxy: Optional[str] = None,
    verify: Optional[bool] = None,
) -> HttpToolResult | FailedToolResult:
    header_file = host.make_temp_path("http_hdr")
    body_file = host.make_temp_path("http_body")

    curl_parts = [
        "curl",
        "-s",
        "-S",
        "-D",
        header_file,
        "-o",
        body_file,
        "-w",
        f"\\n{_WRITEOUT_PREFIX}%{{http_code}}\\t%{{content_type}}",
        "-X",
        method,
        "--max-time",
        str(timeout),
        "--connect-timeout",
        str(min(timeout, 30)),
    ]

    if follow_redirects:
        curl_parts.append("-L")

    if headers:
        for k, v in headers.items():
            curl_parts.extend(["-H", f"{k}: {v}"])

    data_file: str | None = None

    if data is not None:
        data_file = host.make_temp_path("http_data")
        encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
        write_cmd = f"echo '{encoded}' | base64 -d > {shlex.quote(data_file)}"
        rc, _, stderr = await host.execute_raw(write_cmd, timeout=30.0)
        if rc != 0:
            return FailedToolResult(content=f"写入请求数据失败: {stderr}")
        curl_parts.extend(["-d", f"@{data_file}"])

    if json_data is not None:
        data_file = host.make_temp_path("http_json")
        json_str = json.dumps(json_data)
        encoded = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
        write_cmd = f"echo '{encoded}' | base64 -d > {shlex.quote(data_file)}"
        rc, _, stderr = await host.execute_raw(write_cmd, timeout=30.0)
        if rc != 0:
            return FailedToolResult(content=f"写入JSON数据失败: {stderr}")
        curl_parts.extend(["-H", "Content-Type: application/json"])
        curl_parts.extend(["-d", f"@{data_file}"])

    if auth is not None:
        curl_parts.extend(["-u", f"{auth[0]}:{auth[1]}"])

    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        curl_parts.extend(["-b", cookie_str])

    if proxy is not None:
        curl_parts.extend(["-x", proxy])

    if verify is False:
        curl_parts.append("-k")

    if params:
        url = f"{url}?{urlencode(params)}"

    curl_parts.append(url)

    cmd = shlex.join(curl_parts)
    effective_timeout = float(timeout + 15)
    rc, stdout, stderr = await host.execute_raw(cmd, timeout=effective_timeout)

    status_code = 0
    content_type = ""
    for line in reversed(stdout.split("\n")):
        if _WRITEOUT_PREFIX in line:
            info = line.split(_WRITEOUT_PREFIX, 1)[1]
            parts = info.split("\t", 1)
            if len(parts) == 2:
                if parts[0].isdigit():
                    status_code = int(parts[0])
                else:
                    return FailedToolResult(content=f"无法解析HTTP状态码: {parts[0]}")
                content_type = parts[1]
            break

    if status_code == 0:
        error_msg = stderr or stdout
        if "not found" in error_msg.lower():
            return FailedToolResult(content="远程机器没有安装curl")
        return FailedToolResult(content=f"HTTP请求失败: {error_msg}")

    headers_dict: dict[str, str] = {}
    rc_hdr, hdr_b64, _ = await host.execute_raw(
        f"base64 {shlex.quote(header_file)} 2>/dev/null", timeout=10.0
    )
    if rc_hdr == 0 and hdr_b64.strip():
        hdr_bytes = base64.b64decode(hdr_b64.strip())
        hdr_text = hdr_bytes.decode("utf-8", errors="replace")
        for line in hdr_text.split("\n"):
            line = line.strip()
            if ": " in line:
                key, value = line.split(": ", 1)
                headers_dict[key] = value

    body_size_cmd = f"wc -c < {shlex.quote(body_file)} 2>/dev/null || echo 0"
    _, size_str, _ = await host.execute_raw(body_size_cmd, timeout=5.0)
    body_size = int(size_str.strip()) if size_str.strip().isdigit() else 0

    body_bytes = b""
    if body_size > 0:
        rc_body, body_b64, _ = await host.execute_raw(
            f"base64 {shlex.quote(body_file)}", timeout=60.0
        )
        if rc_body == 0 and body_b64.strip():
            body_bytes = base64.b64decode(body_b64.strip())

    cleanup_files = [header_file, body_file]
    if data_file:
        cleanup_files.append(data_file)
    await host.execute_raw(
        f"rm -f {' '.join(shlex.quote(f) for f in cleanup_files)}", timeout=5.0
    )

    return await build_http_message(
        status_code=status_code,
        headers=headers_dict,
        content=body_bytes,
        content_type=content_type,
    )
