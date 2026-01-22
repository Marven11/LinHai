"""通用工具模块，包含不与特定机器相关的工具。"""

from datetime import datetime
import asyncio
import re
import shutil
import subprocess
import tempfile
from typing import Optional, TypedDict, List, Dict

import chardet
import httpx
from bs4 import BeautifulSoup
from selenium import webdriver

from linhai.tool.base import (
    global_tools,
    ToolArgInfo,
    ToolSet,
    ToolResultSuccess,
)
from linhai.group_chat import GroupChat
from linhai.utils import generate_id

# 导入其他通用工具，使其装饰器生效
# calculator和todolist现在定义在本文件中


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


@global_tools.register_tool(
    name="fetch_article",
    desc="抓取网页并转换为Markdown格式，保存原始HTML和转换的markdown到临时目录，返回HTML, markdown的路径和markdown的内容",
    args={
        "url": ToolArgInfo(desc="目标网页URL", type="str"),
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

        with webdriver.Firefox(options=options) as driver:
            driver.get(url)

            soup = BeautifulSoup(driver.page_source, "html.parser")
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("javascript:"):  # type: ignore
                a.decompose()

        for img in soup.find_all("img", src=True):
            src = img.get("src", "")  # type: ignore
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


@global_tools.register_tool(
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

                title = link_elem.get_text(strip=True)  # type: ignore
                link = link_elem.get("href", "")  # type: ignore

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


@global_tools.register_tool(
    name="sleep",
    desc="睡眠X秒，返回开始和结束时间",
    args={"seconds": ToolArgInfo(desc="睡眠的秒数", type="float")},
    required_args=["seconds"],
)
async def sleep_tool(seconds: float) -> ToolResultSuccess:
    start = datetime.now()
    await asyncio.sleep(seconds)
    return ToolResultSuccess(
        content=f"睡眠了{seconds} 秒，从 {start.strftime('%Y-%m-%d %H:%M:%S')} 到 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )


class TodolistItem(TypedDict):
    """Todolist项的类型定义。"""

    id: str
    content: str


class TodolistManager:

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.todolists: Dict[str, str] = {}
        group_chat.register_member("todolist_manager", self)
        group_chat.add_postinit(self.postinit)

    def postinit(self):
        """后初始化：创建todolist工具集并添加到tool_manager"""
        from linhai.tool.main import ToolManager

        tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        todolist_toolset = create_agent_todolist_toolset(self)
        tool_manager.add_toolset(todolist_toolset)

    def add_todolist(self, content: str) -> str:
        if not content or not content.strip():
            raise ValueError("todolist内容不能为空")

        todolist_id = generate_id("todolist")
        self.todolists[todolist_id] = content.strip()
        return todolist_id

    def list_todolists(self) -> List[TodolistItem]:
        return [
            {"id": todolist_id, "content": content}
            for todolist_id, content in self.todolists.items()
        ]

    def get_todolist_by_id(self, todolist_id: str) -> Optional[TodolistItem]:
        if todolist_id not in self.todolists:
            return None
        return {"id": todolist_id, "content": self.todolists[todolist_id]}

    def delete_todolist(self, todolist_id: str) -> str:
        """删除todolist，返回删除结果。"""
        if todolist_id not in self.todolists:
            return f"错误：Todolist ID {todolist_id} 不存在"
        content = self.todolists[todolist_id]
        del self.todolists[todolist_id]
        return f"成功删除todolist: {todolist_id} ({content})"


def create_agent_todolist_toolset(
    todolist_manager: TodolistManager,
) -> ToolSet:
    """创建todolist管理工具集（只有添加和列出功能，供Agent使用）。"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="todolist_add",
        desc="添加todolist",
        args={
            "content": ToolArgInfo(desc="todolist内容", type="str"),
        },
        required_args=["content"],
    )
    def todolist_add(content: str) -> str:
        """添加todolist。"""
        todolist_id = todolist_manager.add_todolist(content)
        return f"成功添加todolist，ID: {todolist_id}"

    @toolset.register_tool(
        name="todolist_list",
        desc="列出所有todolist",
        args={},
        required_args=[],
    )
    def todolist_list() -> str:
        """列出所有todolist。"""
        todolists = todolist_manager.list_todolists()
        if not todolists:
            return "当前没有todolist。"
        return "\n".join(f"{item['id']}: {item['content']}" for item in todolists)

    return toolset


# 计算器工具


def safe_calculator(expression: str) -> str:
    """安全计算数学表达式。只允许安全字符，避免代码执行。

    Args:
        expression: 数学表达式字符串

    Returns:
        计算结果字符串或错误消息
    """
    safe_pattern = r"^[0-9+\-*/().%><\s]+$"
    if not re.match(safe_pattern, expression):
        return "错误: 表达式包含不安全字符。只允许数字、加减乘除(+ - * /)、乘方(**)、取模(%)、大于小于(> <)、括号和空格。"

    if not expression.strip():
        return "错误: 表达式不能为空。"

    try:
        result = eval(expression, {"__builtins__": {}}, {})  # pylint: disable=eval-used
        return str(result)
    except (ValueError, ZeroDivisionError, SyntaxError) as e:
        return f"错误: 计算失败 - {str(e)}"


# 注册计算器工具
@global_tools.register_tool(
    name="safe_calculator",
    desc="安全计算数学表达式。表达式只能包含数字、加减乘除符号(+ - * /)、乘方(**)、取模(%)、大于小于(> <)和空格。建议在计算任何数字时优先使用此工具。",
    args={
        "expression": ToolArgInfo(
            desc="数学表达式，例如 '2 + 3 * 4' 或 '10 % 3'", type="str"
        ),
    },
    required_args=["expression"],
)
def registered_safe_calculator(expression: str) -> str:
    return safe_calculator(expression)
