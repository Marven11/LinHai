"""通用工具模块，包含不与特定机器相关的工具。"""

from datetime import datetime
import asyncio
import shutil
import subprocess
import tempfile
from typing import Optional, TypedDict, List, Dict

import quickjs

import chardet
import httpx
from bs4 import BeautifulSoup
from selenium import webdriver

from linhai.tool.base import (
    utils_tools,
    ToolArgInfo,
    ToolSet,
    ToolResultSuccess,
)
from linhai.registry import Registry
from linhai.utils import generate_id


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


def _download_with_selenium(url: str) -> str:
    """使用selenium下载网页内容"""
    options = webdriver.FirefoxOptions()
    with webdriver.Firefox(options=options) as driver:
        driver.get(url)
        return driver.page_source


def _download_with_httpx(url: str) -> str:
    """使用httpx下载网页内容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
            return response.text
    except httpx.RequestError as e:
        raise RuntimeError(f"HTTP请求失败: {str(e)}") from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"HTTP状态错误: {str(e)}") from e


@utils_tools.register_tool(
    name="fetch_article",
    desc="抓取网页并转换为Markdown格式，保存原始HTML和转换的markdown到临时目录，返回HTML, markdown的路径和markdown的内容",
    args={
        "url": ToolArgInfo(desc="目标网页URL", type="str"),
        "http_downloader": ToolArgInfo(
            desc="HTML下载器，可选值：'none'或'selenium'（默认使用selenium）或'httpx'",
            type="str",
        ),
    },
    required_args=["url"],
)
def fetch_article(url: str, http_downloader: str = "none") -> str:

    if http_downloader not in ("none", "selenium", "httpx"):
        return f"错误: http_downloader参数只能是'none'（默认selenium）、'selenium'或'httpx'，得到'{http_downloader}'"

    with tempfile.NamedTemporaryFile(suffix=".md", delete=True) as file:
        output_md = file.name
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
        output_html = tmp_html.name
    try:
        if http_downloader == "httpx":
            html_content = _download_with_httpx(url)
        else:
            html_content = _download_with_selenium(url)

        soup = BeautifulSoup(html_content, "html.parser")
        for a in soup.find_all("a", href=True):
            href_value = a.get("href", "")
            if isinstance(href_value, str) and href_value.startswith("javascript:"):
                a.decompose()

        for img in soup.find_all("img", src=True):
            src = img.get("src", "")
            if len(str(src)) > 400:
                img.decompose()

        for svg in soup.find_all("svg"):
            svg.decompose()

        with open(output_html, "w", encoding="utf-8") as f:
            f.write(str(soup))
        if shutil.which("pandoc") is None:
            return "错误：pandoc未安装，请先安装pandoc"

        subprocess.run(
            [
                "pandoc",
                output_html,
                "-o",
                output_md,
                "--to=markdown"
                "-header_attributes"
                "-link_attributes"
                "-fenced_code_attributes"
                "-inline_code_attributes"
                "-bracketed_spans"
                "-markdown_in_html_blocks"
                "-raw_html"
                "-fenced_divs"
                "-native_divs"
                "-native_spans"
                "-simple_tables"
                "+pipe_tables",
            ],
            check=True,
        )

        with open(output_md, "r", encoding="utf-8") as f:
            content = f.read()
            return f"""
文件已经保存在: {output_html=} {output_md=} 用户需要时优先提供markdown

markdown内容如下

---

{content}
"""

    except (OSError, subprocess.SubprocessError) as e:
        return f"转换失败: {str(e)}"


@utils_tools.register_tool(
    name="search_web",
    desc="使用DuckDuckGo进行网页搜索并返回格式化结果",
    args={
        "query": ToolArgInfo(desc="搜索查询", type="str"),
        "max_results": ToolArgInfo(desc="最大结果数量（默认5）", type="int"),
    },
    required_args=["query"],
)
async def search_web(query: str, max_results: int = 5) -> str:
    """
    搜索DuckDuckGo并返回格式化的搜索结果
    """
    import urllib.parse

    url = "https://html.duckduckgo.com/html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    data = {
        "q": query,
        "b": "",
        "kl": "",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            if not soup:
                return "解析HTML响应失败"

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
                    link = urllib.parse.unquote(
                        str(link).split("uddg=")[1].split("&")[0]
                    )

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
                return "未找到相关搜索结果。可能是由于DuckDuckGo的机器人检测或查询无匹配结果。请尝试重新表述搜索或稍后重试。"

            output = []
            output.append(f"找到 {len(results)} 个搜索结果：\n")

            for result in results:
                output.append(f"{result['position']}. {result['title']}")
                output.append(f"   URL: {result['link']}")
                output.append(f"   摘要: {result['snippet']}")
                output.append("")

            return "\n".join(output)

    except httpx.RequestError as e:
        return f"搜索请求失败: {str(e)}"
    except (ConnectionError, TimeoutError, OSError) as e:
        return f"搜索过程中发生错误: {str(e)}"


@utils_tools.register_tool(
    name="quickjs_calculator",
    desc="使用quickjs计算数学表达式。直接eval JavaScript表达式。建议在计算任何数字时优先使用此工具。",
    args={
        "expression": ToolArgInfo(
            desc="数学表达式，例如 '2 + 3 * 4' 或 '10 % 3'", type="str"
        ),
    },
    required_args=["expression"],
)
def quickjs_calculator(expression: str) -> str:
    ctx = quickjs.Context()
    return str(ctx.eval(expression))


def generate_sleep_toolset(registry: Registry) -> ToolSet:
    """生成sleep工具集，包含可打断的sleep工具。

    Args:
        registry: Registry实例，用于检查新用户消息

    Returns:
        ToolSet实例，包含sleep工具
    """
    from datetime import datetime
    from linhai.tool.base import ToolArgInfo, ToolSet, ToolResultSuccess

    sleep_toolset = ToolSet()

    @sleep_toolset.register_tool(
        name="sleep",
        desc="睡眠X秒，返回开始和结束时间",
        args={"seconds": ToolArgInfo(desc="睡眠的秒数", type="float")},
        required_args=["seconds"],
    )
    async def sleep_tool(seconds: float) -> ToolResultSuccess:
        start = datetime.now()
        while True:
            elapsed = (datetime.now() - start).total_seconds()
            if elapsed >= seconds:
                break
            if not registry.is_empty("user_message"):
                return ToolResultSuccess(
                    content=f"有新用户消息，sleep已打断。已睡眠{elapsed}秒，从 {start.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
            remaining = seconds - elapsed
            sleep_time = min(1.0, remaining)
            await asyncio.sleep(sleep_time)
        return ToolResultSuccess(
            content=f"睡眠了{seconds} 秒，从 {start.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    return sleep_toolset
