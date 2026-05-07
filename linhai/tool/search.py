import asyncio
import urllib.parse
from typing import Optional, TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup

from linhai.tool.base import (
    ToolSet,
    ToolArgInfo,
    ToolResult,
    SuccessfulToolResult,
    FailedToolResult,
)
from linhai.utils.i18n import t

if TYPE_CHECKING:
    from linhai.config import WebSearchConfig


def _search_duckduckgo_http(query: str, max_results: int) -> ToolResult:
    url = "https://html.duckduckgo.com/html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    data = {
        "q": query,
        "b": "",
        "kl": "",
    }

    with httpx.Client() as client:
        response = client.post(url, data=data, headers=headers, timeout=30.0)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    if not soup:
        return FailedToolResult(content="解析HTML响应失败")

    results = []
    for result in soup.select(".result"):
        title_elem = result.select_one(".result__title")
        if not title_elem:
            continue

        link_elem = title_elem.find("a")
        if not link_elem:
            continue

        title = link_elem.get_text(strip=True)
        link = link_elem.get("href", "")

        if link and "y.js" in link:
            continue

        if link and str(link).startswith("//duckduckgo.com/l/?uddg="):
            link = urllib.parse.unquote(str(link).split("uddg=")[1].split("&")[0])

        snippet_elem = result.select_one(".result__snippet")
        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

        results.append(
            {
                "title": title,
                "link": link,
                "snippet": snippet,
                "position": len(results) + 1,
            }
        )

        if len(results) >= max_results:
            break

    if not results:
        return FailedToolResult(
            content="未找到相关搜索结果。可能是由于DuckDuckGo的机器人检测或查询无匹配结果。请尝试重新表述搜索或稍后重试。"
        )

    output = [f"找到 {len(results)} 个搜索结果：\n"]
    for result in results:
        output.append(f"{result['position']}. {result['title']}")
        output.append(f"   URL: {result['link']}")
        output.append(f"   摘要: {result['snippet']}")
        output.append("")

    return SuccessfulToolResult(content="\n".join(output))


def _search_bigmodel(query: str, max_results: int, api_key: str) -> ToolResult:
    url = "https://open.bigmodel.cn/api/paas/v4/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "search_query": query,
        "search_engine": "search_std",
        "search_intent": False,
        "count": max_results,
    }

    with httpx.Client() as client:
        response = client.post(url, json=payload, headers=headers, timeout=30.0)
        response.raise_for_status()

    data = response.json()
    search_results = data.get("search_result", [])

    if not search_results:
        return FailedToolResult(content="BigModel搜索未返回结果。")

    results = []
    for item in search_results[:max_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("content", ""),
                "position": len(results) + 1,
            }
        )

    output = [f"找到 {len(results)} 个搜索结果：\n"]
    for result in results:
        output.append(f"{result['position']}. {result['title']}")
        output.append(f"   URL: {result['link']}")
        output.append(f"   摘要: {result['snippet']}")
        output.append("")

    return SuccessfulToolResult(content="\n".join(output))


def create_web_search_toolset(config: Optional["WebSearchConfig"]) -> ToolSet:
    from linhai.config import WebSearchConfig

    toolset = ToolSet()
    effective_config = config if config is not None else WebSearchConfig()
    provider_type = effective_config.type

    @toolset.register_tool(
        name="web_search",
        desc=t(
            {
                "zh_CN": "使用搜索引擎进行网页搜索并返回格式化结果",
                "en": "Search the web and return formatted results",
            }
        ),
        args={
            "query": ToolArgInfo(
                desc=t({"zh_CN": "搜索查询", "en": "Search query"}),
                type="str",
            ),
            "max_results": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "最大结果数量（默认5）",
                        "en": "Maximum number of results (default 5)",
                    }
                ),
                type="int",
            ),
        },
        required_args=["query"],
    )
    async def web_search(query: str, max_results: int = 5) -> ToolResult:
        if provider_type == "bigmodel":
            api_key = effective_config.api_key
            if api_key is None:
                return FailedToolResult(content="BigModel搜索需要配置api_key")
            return await asyncio.to_thread(
                _search_bigmodel, query, max_results, api_key
            )
        return await asyncio.to_thread(_search_duckduckgo_http, query, max_results)

    return toolset
