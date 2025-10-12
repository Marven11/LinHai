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
    # 创建临时Lua filter文件
    with tempfile.NamedTemporaryFile(
        suffix=".lua", delete=False, mode="w", encoding="utf-8"
    ) as tmp_lua:
        tmp_lua_path = tmp_lua.name
        lua_filter_content = """
function Table(tbl)
  -- 删除表格属性
  tbl.attr = {}
  -- 删除列属性
  for i, colspec in ipairs(tbl.colspecs) do
    colspec.attr = {}
  end
  -- 删除表头属性
  if tbl.head then
    tbl.head.attr = {}
    for i, row in ipairs(tbl.head.rows) do
      row.attr = {}
      for j, cell in ipairs(row.cells) do
        cell.attr = {}
      end
    end
  end
  -- 删除表体属性
  for i, body in ipairs(tbl.bodies) do
    body.attr = {}
    for j, row in ipairs(body.rows) do
      row.attr = {}
      for k, cell in ipairs(row.cells) do
        cell.attr = {}
      end
    end
  end
  -- 转换为HTML
  return pandoc.RawBlock('html', pandoc.write(pandoc.Pandoc({tbl}), 'html'))
end
"""
        tmp_lua.write(lua_filter_content)
        tmp_lua.flush()

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

            # 删除URL过长的image元素
            for img in soup.find_all("img", src=True):
                if len(img["src"]) > 800:
                    img.decompose()

        with open(tmp_html_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        # 转换为Markdown
        if shutil.which("pandoc") is None:
            return "错误：pandoc未安装，请先安装pandoc"

        subprocess.run(
            [
                "pandoc",
                tmp_html_path,
                "-o",
                output_md,
                "--lua-filter",
                tmp_lua_path,
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
        if os.path.exists(tmp_lua_path):
            os.unlink(tmp_lua_path)

@register_tool(
    name="search_web",
    desc="使用DuckDuckGo进行网页搜索并返回格式化结果",
    args={
        "query": {"desc": "搜索查询", "type": "str"},
        "max_results": {"desc": "最大结果数量（默认5）", "type": "int"},
    },
    required_args=["query"],
)
def search_web(query: str, max_results: int = 5) -> str:
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
        response = requests.post(url, data=data, headers=headers, timeout=30)
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
            
            # 跳过广告结果
            if "y.js" in link:
                continue
                
            # 清理DuckDuckGo重定向URL
            if link.startswith("//duckduckgo.com/l/?uddg="):
                link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])
            
            snippet_elem = result.select_one(".result__snippet")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            
            results.append({
                "title": title,
                "link": link,
                "snippet": snippet,
                "position": len(results) + 1
            })
            
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
        
    except requests.RequestException as e:
        return f"搜索请求失败: {str(e)}"
    except Exception as e:
        return f"搜索过程中发生错误: {str(e)}"