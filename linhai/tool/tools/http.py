"""HTTP工具模块，提供发送HTTP请求的功能。"""

from typing import Optional
import requests
import httpx

from linhai.tool.base import global_tools

import os
import tempfile
import subprocess
import shutil
from bs4 import BeautifulSoup
from selenium import webdriver


@global_tools.register_tool(
    name="http_request",
    desc="使用httpx库发送HTTP请求并获取响应内容",
    args={
        "method": {"desc": "HTTP方法，如GET、POST", "type": "str"},
        "url": {"desc": "请求的URL", "type": "str"},
        "params": {"desc": "查询参数（字典形式）", "type": "Optional[dict]"},
        "headers": {"desc": "请求头（字典形式）", "type": "Optional[dict]"},
        "data": {"desc": "请求体数据", "type": "Optional[str]"},
        "follow_redirects": {"desc": "是否跟随重定向，默认True", "type": "bool"},
    },
    required_args=["method", "url"],
)
async def http_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    data: Optional[str] = None,
    follow_redirects: bool = True,
) -> str:
    """
    发送HTTP请求并返回响应内容
    """
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
            return response.text
    except httpx.RequestError as e:
        return f"请求失败: {str(e)}"


@global_tools.register_tool(
    name="fetch_article",
    desc="抓取网页并转换为Markdown格式，保存原始HTML和转换的markdown到临时目录，返回HTML, markdown的路径和markdown的内容",
    args={
        "url": {"desc": "目标网页URL", "type": "str"},
    },
    required_args=["url"],
)
def fetch_article(url: str) -> str:
    """抓取指定URL的网页内容并转换为Markdown格式"""
    with tempfile.NamedTemporaryFile(suffix=".md", delete=True) as file:
        output_md = file.name
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
        output_html = tmp_html.name
    try:
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        with webdriver.Firefox(options=options) as driver:
            driver.get(url)

            # 删除javascript:链接
            soup = BeautifulSoup(driver.page_source, "html.parser")
            for a in soup.find_all("a", href=True):
                if a["href"].startswith("javascript:"):  # type: ignore
                    a.decompose()

            # 删除无用image元素
            for img in soup.find_all("img", src=True):
                src = img.get("src", "")  # type: ignore
                if len(str(src)) > 400:
                    img.decompose()

            for svg in soup.find_all("svg"):
                svg.decompose()

        with open(output_html, "w", encoding="utf-8") as f:
            f.write(str(soup))

        # 转换为Markdown
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

    except Exception as e:
        return f"转换失败: {str(e)}"


@global_tools.register_tool(
    name="search_web",
    desc="使用DuckDuckGo进行网页搜索并返回格式化结果",
    args={
        "query": {"desc": "搜索查询", "type": "str"},
        "max_results": {"desc": "最大结果数量（默认5）", "type": "int"},
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

                title = link_elem.get_text(strip=True)  # type: ignore
                link = link_elem.get("href", "")  # type: ignore

                # 跳过广告结果
                if link and "y.js" in link:
                    continue

                # 清理DuckDuckGo重定向URL
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
                return "未找到相关搜索结果。可能是由于DuckDuckGo的机器人检测或查询无匹配结果。请尝试重新表述搜索或稍后重试。"

            # 格式化结果
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
    except Exception as e:
        return f"搜索过程中发生错误: {str(e)}"
