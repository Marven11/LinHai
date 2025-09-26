#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文章抓取与转换演示

本示例展示了如何:
1. 使用Selenium抓取网页内容
2. 保存HTML到临时文件
3. 使用pandoc将HTML转换为Markdown

使用前请确保已安装:
- selenium
- webdriver-manager
- pandoc (系统级安装)
"""

import os
import tempfile
import subprocess
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options


def fetch_and_convert(url: str, output_md: str = "output.md") -> str:
    """
    抓取指定URL的网页内容并转换为Markdown格式

    Args:
        url: 要抓取的网页URL
        output_md: 输出的Markdown文件路径

    Returns:
        转换后的Markdown内容
    """
    # 创建临时HTML文件
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_html:
        tmp_html_path = tmp_html.name

    try:
        # 使用Selenium抓取网页
        print(f"正在抓取网页: {url}")
        driver = webdriver.Firefox()
        driver.get(url)

        # 保存HTML内容
        html_content = driver.page_source

        # 删除javascript:开头的链接
        soup = BeautifulSoup(html_content, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            if a_tag["href"].startswith("javascript:"):  # type: ignore
                a_tag.decompose()
        html_content = str(soup)

        with open(tmp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"HTML已保存到: {tmp_html_path}")

        # 使用pandoc转换为Markdown
        print(f"正在使用pandoc转换为Markdown...")
        pandoc_cmd = [
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
            "+simple_tables"
            "+pipe_tables",
        ]

        result = subprocess.run(pandoc_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"pandoc转换失败: {result.stderr}")

        # 读取转换后的Markdown
        with open(output_md, "r", encoding="utf-8") as f:
            md_content = f.read()

        print(f"Markdown已生成: {output_md}")
        return md_content

    finally:
        # 清理临时文件
        if os.path.exists(tmp_html_path):
            os.unlink(tmp_html_path)

        # 关闭浏览器
        if "driver" in locals():
            driver.quit()


def main():
    """演示函数"""
    print("===== 文章抓取与转换演示 =====")

    # 示例URL - 可替换为实际需要抓取的URL
    example_url = "https://mp.weixin.qq.com/s/wTlublMBSsYqwyKiSyE3vg"

    try:
        # 执行抓取和转换
        md_content = fetch_and_convert(example_url)

        # 显示前200个字符作为预览
        print("\n转换后的Markdown预览:")
        print("-" * 50)
        print(md_content[:200] + ("..." if len(md_content) > 200 else ""))
        print("-" * 50)

        print("\n演示完成! 完整Markdown已保存到 output.md")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")


if __name__ == "__main__":
    main()
