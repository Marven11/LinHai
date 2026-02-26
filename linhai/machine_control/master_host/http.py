"""HTTP工具模块，提供发送HTTP请求的功能。"""

from typing import Optional
import json
import re
import tempfile

import chardet
import httpx
from linhai.tool.base import ToolResultFailed, ToolResultSuccess


def analyze_content(content_type: str, content: bytes) -> tuple[bool, Optional[str]]:
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
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".bin"
                ) as tmp_file:
                    tmp_file.write(response.content)
                    filepath = tmp_file.name
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
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".txt", mode="w", encoding="utf-8"
                    ) as tmp_file:
                        tmp_file.write(text_content)
                        filepath = tmp_file.name
                    result_parts.extend(
                        [
                            "<<is_binary>>false<<is_binary>>",
                            f"<<size>>{len(text_content)}<<size>>",
                            f"<<body_file>>{filepath}<<body_file>>",
                        ]
                    )
                else:
                    result_parts.extend(
                        [
                            "<<is_binary>>false<<is_binary>>",
                            f"<<size>>{len(text_content)}<<size>>",
                            f"<<body>>{text_content}<<body>>",
                        ]
                    )

                content_str = "\n".join(result_parts)
                return ToolResultSuccess(content=content_str)
    except httpx.RequestError as e:
        return ToolResultFailed(content=f"请求失败: {str(e)}")
