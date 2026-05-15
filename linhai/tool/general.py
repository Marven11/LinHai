"""通用工具模块，包含不与特定机器相关的工具。"""

import shutil
import subprocess
import tempfile
from typing import Optional

import quickjs

import chardet
import httpx
from bs4 import BeautifulSoup

from linhai.tool.base import (
    utils_tools,
    ToolArgInfo,
    SuccessfulToolResult,
    FailedToolResult,
    ToolResult,
    WebpageFetchToolResult,
)
from linhai.utils.i18n import t


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


def _find_chromium_binary() -> Optional[str]:
    for name in ("chromium", "chromium-browser", "chrome", "google-chrome-stable"):
        path = shutil.which(name)
        if path is not None:
            return path
    return None


def _download_with_chromium(url: str) -> str:
    chromium_path = _find_chromium_binary()
    if chromium_path is None:
        raise RuntimeError("chrome/chromium未安装，请先安装chrome或chromium")
    result = subprocess.run(
        [
            chromium_path,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--virtual-time-budget=8000",
            "--dump-dom",
            url,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"chromium下载失败: {result.stderr}")
    return result.stdout


def _download_with_httpx(url: str) -> str:
    """使用httpx下载网页内容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/markdown, text/html, */*",
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
    name="fetch_webpage",
    desc=t(
        {
            "zh_CN": "抓取静态网页并转换为Markdown格式，保存原始HTML和转换的markdown到临时目录，返回HTML, markdown的路径和markdown的内容。此工具只能爬取静态页面，无法处理需要动态交互的内容",
            "en": "Fetch a static webpage and convert to Markdown format, save raw HTML and converted markdown to temp directory, return paths and markdown content. This tool can only crawl static pages and cannot handle content requiring dynamic interaction",
        }
    ),
    args={
        "url": ToolArgInfo(
            desc=t({"zh_CN": "目标网页URL", "en": "Target webpage URL"}), type="str"
        ),
        "http_downloader": ToolArgInfo(
            desc=t(
                {
                    "zh_CN": "HTML下载器，必须指定'chromium'或'httpx'",
                    "en": "HTML downloader, must be 'chromium' or 'httpx'",
                }
            ),
            type="str",
        ),
    },
    required_args=["url", "http_downloader"],
)
def fetch_webpage(url: str, http_downloader: str):

    if http_downloader not in ("chromium", "httpx"):
        return FailedToolResult(
            content=f"错误: http_downloader参数只能是'chromium'或'httpx'，得到'{http_downloader}'"
        )

    with tempfile.NamedTemporaryFile(suffix=".md", delete=True) as file:
        output_md = file.name
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
        output_html = tmp_html.name
    try:
        if http_downloader == "httpx":
            html_content = _download_with_httpx(url)
        else:
            html_content = _download_with_chromium(url)

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
            return FailedToolResult(content="错误：pandoc未安装，请先安装pandoc")

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
            return WebpageFetchToolResult(
                html_path=output_html, md_path=output_md, content=content
            )

    except (OSError, subprocess.SubprocessError) as e:
        return FailedToolResult(content=f"转换失败: {str(e)}")


@utils_tools.register_tool(
    name="quickjs_calculator",
    desc=t(
        {
            "zh_CN": "使用quickjs计算数学表达式。直接eval JavaScript表达式。建议在计算任何数字时优先使用此工具。",
            "en": "Evaluate math expressions using quickjs. Directly eval JavaScript expressions. Recommended to use this tool first when calculating numbers.",
        }
    ),
    args={
        "expression": ToolArgInfo(
            desc=t(
                {
                    "zh_CN": "数学表达式，例如 '2 + 3 * 4' 或 '10 % 3'",
                    "en": "Math expression, e.g. '2 + 3 * 4' or '10 % 3'",
                }
            ),
            type="str",
        ),
    },
    required_args=["expression"],
)
def quickjs_calculator(expression: str) -> ToolResult:
    ctx = quickjs.Context()
    return SuccessfulToolResult(content=str(ctx.eval(expression)))
