"""HTTP工具模块，提供发送HTTP请求的功能。"""

from typing import Optional
import tempfile
import re
import json
import os
import hashlib
import time

import chardet
import httpx
from linhai.tool.base import ToolResultSuccess, ToolResultFailed


def analyze_content(content_type: str, content: bytes) -> tuple[bool, Optional[str]]:
    """分析HTTP响应内容，返回是否为二进制和检测到的编码。

    通过Content-Type和chardet编码检测综合判断，避免重复检测。
    """
    if (
        content_type.startswith("image/")
        or content_type.startswith("application/octet-stream")
        or content_type.startswith("application/pdf")
        or content_type.startswith("application/zip")
        or content_type.startswith("audio/")
        or content_type.startswith("video/")
        or "binary" in content_type
        or content_type.startswith("font/")
        or content_type.startswith("application/vnd.")
    ):
        return True, None

    if result := re.search(r"charset=(.+)", content_type):
        return False, result.group(1)

    detected = chardet.detect(content)
    encoding = detected["encoding"]

    if encoding is None:
        return True, None

    return False, encoding


async def http_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    data: Optional[str] = None,
    follow_redirects: bool = True,
    timeout: int = 60,
) -> ToolResultSuccess | ToolResultFailed:
    """
    发送HTTP请求并返回响应内容或文件路径
    """
    if headers is None:
        headers = {}
    headers.setdefault(
        "User-Agent", "Mozilla/5.0 (compatible; LinHai/1.0; Chrome-like)"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                follow_redirects=follow_redirects,
                data=data,  # type: ignore[arg-type]
                timeout=timeout,
            )

            content_type = response.headers.get("content-type", "").lower()
            status_code = response.status_code
            response_headers = dict(response.headers)

            is_binary, encoding = analyze_content(content_type, response.content)

            if is_binary:
                content_hash = hashlib.md5(response.content).hexdigest()[:8]
                filename = f"{int(time.time())}_{content_hash}.bin"
                filepath = os.path.join(
                    "/home/cube/.local/share/linhai/conversation/1a28cf90-1879-47ae-8fba-70f68fad80f0/http_responses",
                    filename
                )
                with open(filepath, "wb") as f:
                    f.write(response.content)
                result_parts = [
                    f"<<status_code>>{status_code}<<status_code>>",
                    f"<<headers>>{json.dumps(response_headers)}<<headers>>",
                    "<<is_binary>>true<<is_binary>>",
                    f"<<size>>{len(response.content)}<<size>>",
                    f"<<body_file>>{filepath}<<body_file>>",
                ]
                content_str = "\n".join(result_parts)
                return ToolResultSuccess(content=content_str)
            else:
                # 文本内容
                if encoding:
                    try:
                        text_content = response.content.decode(encoding)
                    except UnicodeDecodeError:
                        return ToolResultFailed(
                            content=f"无法使用编码 {encoding} 解码响应内容"
                        )
                else:
                    text_content = response.text
                result_parts = [
                    f"<<status_code>>{status_code}<<status_code>>",
                    f"<<headers>>{json.dumps(response_headers)}<<headers>>",
                ]
                if len(text_content) > 5000:
                    content_hash = hashlib.md5(text_content.encode()).hexdigest()[:8]
                    filename = f"{int(time.time())}_{content_hash}.txt"
                    filepath = os.path.join(
                        "/home/cube/.local/share/linhai/conversation/1a28cf90-1879-47ae-8fba-70f68fad80f0/http_responses",
                        filename
                    )
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(text_content)
                    result_parts.extend([
                        "<<is_binary>>false<<is_binary>>",
                        f"<<size>>{len(text_content)}<<size>>",
                        f"<<body_file>>{filepath}<<body_file>>",
                    ])
                else:
                    result_parts.extend([
                        "<<is_binary>>false<<is_binary>>",
                        f"<<size>>{len(text_content)}<<size>>",
                        f"<<body>>{text_content}<<body>>",
                    ])
                
                content_str = "\n".join(result_parts)
                return ToolResultSuccess(content=content_str)
    except httpx.RequestError as e:
        return ToolResultFailed(content=f"请求失败: {str(e)}")
