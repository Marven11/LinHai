"""HTTP工具模块，提供发送HTTP请求的功能。"""

from typing import Optional
import requests

from linhai.tool.base import register_tool

import os
import tempfile
import subprocess
import shutil
from bs4 import BeautifulSoup
from selenium import webdriver


@register_tool(
    name="http_request",
    desc="使用requests库发送HTTP请求并获取响应内容",
    args={
        "method": {"desc": "HTTP方法，如GET、POST", "type": "str"},
        "url": {"desc": "请求的URL", "type": "str"},
        "params": {"desc": "查询参数（字典形式）", "type": "Optional[dict]"},
        "headers": {"desc": "请求头（字典形式）", "type": "Optional[dict]"},
        "data": {"desc": "请求体数据", "type": "Optional[str]"},
    },
    required_args=["method", "url"],
)
def http_request(
    method: str,
    url: str,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
    data: Optional[str] = None,
) -> str:
    """
    发送HTTP请求并返回响应内容
    """
    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            timeout=10,
        )
        return response.text
    except requests.RequestException as e:
        return f"请求失败: {str(e)}"


@register_tool(
    name="fetch_article",
    desc="抓取网页并转换为Markdown格式",
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
        tmp_html_path = tmp_html.name
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

        with open(tmp_html_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        # 转换为Markdown
        if shutil.which('pandoc') is None:
            return "错误：pandoc未安装，请先安装pandoc"

        subprocess.run(
            [
                "pandoc",
                tmp_html_path,
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
                "-native_divs-native_spans"
                "+pipe_tables",
            ],
            check=True,
        )

        with open(output_md, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        return f"转换失败: {str(e)}"
    finally:
        if os.path.exists(tmp_html_path):
            os.unlink(tmp_html_path)
