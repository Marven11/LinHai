import asyncio
from typing import Any, Optional

import httpx

from linhai.machine_control.http_message import (
    HttpToolResult,
    HttpTextDiffToolResult,
    build_http_message,
)
from linhai.tool.base import FailedToolResult
from linhai.utils.http_diff import http_diff
from linhai.utils.tokenizer import count_tokens

_history_files: list[str] = []
_MAX_HISTORY = 5
_DIFF_TOKEN_LIMIT = 2000


async def http_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    data: Optional[str] = None,
    follow_redirects: bool = False,
    timeout: int = 60,
    auth: Optional[tuple[str, str]] = None,
    cookies: Optional[dict] = None,
    json_data: Optional[dict] = None,
    proxy: Optional[str] = None,
    verify: Optional[bool] = None,
) -> HttpToolResult | HttpTextDiffToolResult | FailedToolResult:
    headers = headers or {}
    headers.setdefault(
        "User-Agent", "Mozilla/5.0 (compatible; LinHai/1.0; Chrome-like)"
    )
    client_kwargs: dict[str, Any] = {}
    if proxy is not None:
        client_kwargs["proxy"] = proxy
    if verify is not None:
        client_kwargs["verify"] = verify
    async with httpx.AsyncClient(**client_kwargs) as client:
        results = await asyncio.gather(
            client.request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                follow_redirects=follow_redirects,
                content=data,
                timeout=timeout,
                auth=auth,
                cookies=cookies,
                json=json_data,
            ),
            return_exceptions=True,
        )
        result = results[0]
        if isinstance(result, httpx.RequestError):
            return FailedToolResult(content=f"请求失败: {str(result)}")
        if isinstance(result, BaseException):
            return FailedToolResult(
                content=f"处理响应失败: {type(result).__name__}: {str(result)}"
            )
        response = result
        msg = await build_http_message(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            content_type=response.headers.get("content-type", "").lower(),
        )
        if not isinstance(msg, HttpToolResult) or msg.body_file is None:
            return msg

        if msg.is_binary:
            return msg

        body_text = _read_file(msg.body_file)
        for hist_file in _history_files:
            diff_text = http_diff(hist_file, msg.body_file)
            diff_tokens = count_tokens(diff_text)
            if diff_tokens < _DIFF_TOKEN_LIMIT:
                diff_result = HttpTextDiffToolResult(
                    http_result=msg,
                    fromfile=hist_file,
                    tofile=msg.body_file,
                    content_diff=diff_text,
                )
                _add_to_history(msg.body_file)
                return diff_result

        _add_to_history(msg.body_file)
        return msg


def _read_file(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def _add_to_history(filepath: str) -> None:
    global _history_files
    _history_files.append(filepath)
    while len(_history_files) > _MAX_HISTORY:
        _history_files.pop(0)
