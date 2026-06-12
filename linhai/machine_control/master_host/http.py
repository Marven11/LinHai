import asyncio
from typing import Any, Optional

import httpx

from linhai.machine_control.http_message import HttpToolResult, build_http_message
from linhai.tool.base import FailedToolResult


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
) -> HttpToolResult | FailedToolResult:
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
        return await build_http_message(
            status_code=response.status_code,
            headers=dict(response.headers),
            content=response.content,
            content_type=response.headers.get("content-type", "").lower(),
        )
