"""HTTP工具模块，提供发送HTTP请求的功能。"""

from typing import Optional
import json
import re
import tempfile
import chardet
import httpx
from linhai.tool.base import ToolResultFailed, ToolResultSuccess


def _is_binary(content_type: str, content: bytes) -> tuple[bool, Optional[str]]:
    """返回 (is_binary, encoding)。"""
    binary_prefixes = {
        "image/",
        "application/octet-stream",
        "application/pdf",
        "application/zip",
        "audio/",
        "video/",
        "font/",
        "application/vnd.",
    }
    if (
        any(content_type.startswith(prefix) for prefix in binary_prefixes)
        or "binary" in content_type
    ):
        return True, None
    if result := re.search(r"charset=(.+)", content_type):
        return False, result.group(1)
    detected = chardet.detect(content)
    encoding = detected["encoding"]
    return (True, None) if encoding is None else (False, encoding)


async def http_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    data: Optional[str] = None,
    follow_redirects: bool = True,
    timeout: int = 60,
) -> ToolResultSuccess | ToolResultFailed:
    """发送HTTP请求并返回响应内容或文件路径。"""
    headers = headers or {}
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
            content = response.content

            is_binary, encoding = _is_binary(content_type, content)
            result_parts = [
                f"<<status_code>>{status_code}<<status_code>>",
                f"<<headers>>{json.dumps(response_headers)}<<headers>>",
                f"<<is_binary>>{'true' if is_binary else 'false'}<<is_binary>>",
            ]

            if is_binary:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
                    f.write(content)
                    filepath = f.name
                result_parts.extend(
                    [
                        f"<<size>>{len(content)}<<size>>",
                        f"<<body_file>>{filepath}<<body_file>>",
                    ]
                )
                return ToolResultSuccess(content="\n".join(result_parts))

            assert encoding is not None, "文本内容，encoding一定不为None"
            try:
                text_content = content.decode(encoding)
            except UnicodeDecodeError:
                return ToolResultFailed(content=f"无法使用编码 {encoding} 解码响应内容")

            size = len(text_content)
            result_parts.append(f"<<size>>{size}<<size>>")
            if size > 5000:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".txt", mode="w", encoding="utf-8"
                ) as f:
                    f.write(text_content)
                    filepath = f.name
                result_parts.append(f"<<body_file>>{filepath}<<body_file>>")
            else:
                result_parts.append(f"<<body>>{text_content}<<body>>")
            return ToolResultSuccess(content="\n".join(result_parts))
    except httpx.RequestError as e:
        return ToolResultFailed(content=f"请求失败: {str(e)}")
