"""HTTP工具模块，提供发送HTTP请求的功能。"""

from typing import Optional
import tempfile

import chardet
import httpx
from linhai.tool.base import ToolResultMessage, ToolErrorMessage


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
) -> ToolResultMessage | ToolErrorMessage:
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
                timeout=10.0,
            )

            content_type = response.headers.get("content-type", "").lower()

            is_binary, encoding = analyze_content(content_type, response.content)

            if is_binary:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".bin"
                ) as tmp_file:
                    tmp_file.write(response.content)
                    return ToolResultMessage(
                        f"二进制内容已保存到临时文件: {tmp_file.name}"
                    )
            else:
                if encoding:
                    try:
                        content = response.content.decode(encoding)
                        return ToolResultMessage(content)
                    except UnicodeDecodeError:
                        return ToolErrorMessage(f"无法使用编码 {encoding} 解码响应内容")
                else:
                    try:
                        return ToolResultMessage(response.text)
                    except UnicodeDecodeError:
                        return ToolErrorMessage("无法解码响应内容，可能是二进制数据")
    except httpx.RequestError as e:
        return ToolErrorMessage(f"请求失败: {str(e)}")
