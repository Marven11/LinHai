"""Unit tests for HTTP tools."""

import unittest
import unittest.mock
import tempfile
import os

from linhai.tool.base import call_tool, global_tools
from linhai.tool.tools.http import fetch_article


class TestFetchArticleTool(unittest.TestCase):
    """Test cases for the fetch_article tool."""

    def setUp(self):
        # 清空工具注册表
        global_tools.clear()
        # 注册fetch_article工具
        global_tools["fetch_article"] = {
            "name": "fetch_article",
            "func": fetch_article,
            "desc": "抓取网页并转换为Markdown格式",
            "args": {
                "url": {"desc": "目标网页URL", "type": "str"},
            },
            "required": ["url"],
        }

    @unittest.mock.patch("linhai.tool.tools.http.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.tools.http.shutil.which")
    @unittest.mock.patch("linhai.tool.tools.http.subprocess.run")
    def test_fetch_article_success(self, mock_subprocess, mock_which, mock_driver):
        """测试fetch_article工具成功转换网页为Markdown"""
        # 模拟pandoc已安装
        mock_which.return_value = "/usr/bin/pandoc"
        
        # 模拟webdriver行为
        mock_driver_instance = mock_driver.return_value.__enter__.return_value
        mock_driver_instance.page_source = """
        <html>
        <body>
            <h1>测试标题</h1>
            <p>测试段落</p>
            <table>
                <tr><th>列1</th><th>列2</th></tr>
                <tr><td>数据1</td><td>数据2</td></tr>
            </table>
            <img src="http://example.com/short.jpg" alt="短URL图片">
            <img src="http://example.com/" + "a" * 800 + ".jpg" alt="长URL图片">
            <a href="javascript:void(0)">JavaScript链接</a>
        </body>
        </html>
        """
        
        # 模拟pandoc转换成功
        with tempfile.NamedTemporaryFile(suffix=".md", mode='w', encoding='utf-8', delete=False) as tmp_md:
            tmp_md_path = tmp_md.name
            tmp_md.write("# 测试标题\n\n测试段落\n\n<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n\n![短URL图片](http://example.com/short.jpg)\n")
            tmp_md.flush()
        
        mock_subprocess.return_value = None  # subprocess.run成功
        
        # 模拟文件读取
        with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data="# 测试标题\n\n测试段落\n\n<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n\n![短URL图片](http://example.com/short.jpg)\n")):
            result = call_tool("fetch_article", {"url": "http://example.com"})
        
        # 验证结果包含转换后的Markdown
        self.assertIn("测试标题", result)
        self.assertIn("测试段落", result)
        # 验证表格以HTML形式输出
        self.assertIn("<table>", result)
        self.assertIn("<tr>", result)
        # 验证长URL图片被删除（只应包含短URL图片）
        self.assertIn("short.jpg", result)
        self.assertNotIn("a" * 800, result)
        # 验证JavaScript链接被删除
        self.assertNotIn("javascript:", result)
        
        # 清理临时文件
        if os.path.exists(tmp_md_path):
            os.unlink(tmp_md_path)

    @unittest.mock.patch("linhai.tool.tools.http.shutil.which")
    def test_fetch_article_pandoc_not_installed(self, mock_which):
        """测试pandoc未安装的情况"""
        # 模拟pandoc未安装
        mock_which.return_value = None
        
        result = call_tool("fetch_article", {"url": "http://example.com"})
        
        self.assertEqual(result, "错误：pandoc未安装，请先安装pandoc")

    @unittest.mock.patch("linhai.tool.tools.http.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.tools.http.shutil.which")
    def test_fetch_article_webdriver_error(self, mock_which, mock_driver):
        """测试webdriver出错的情况"""
        # 模拟pandoc已安装
        mock_which.return_value = "/usr/bin/pandoc"
        
        # 模拟webdriver抛出异常
        mock_driver.side_effect = Exception("WebDriver错误")
        
        result = call_tool("fetch_article", {"url": "http://example.com"})
        
        self.assertIn("转换失败: WebDriver错误", result)

    @unittest.mock.patch("linhai.tool.tools.http.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.tools.http.shutil.which")
    @unittest.mock.patch("linhai.tool.tools.http.subprocess.run")
    def test_fetch_article_pandoc_error(self, mock_subprocess, mock_which, mock_driver):
        """测试pandoc转换出错的情况"""
        # 模拟pandoc已安装
        mock_which.return_value = "/usr/bin/pandoc"
        
        # 模拟webdriver行为
        mock_driver_instance = mock_driver.return_value.__enter__.return_value
        mock_driver_instance.page_source = "<html><body>测试内容</body></html>"
        
        # 模拟pandoc转换失败
        mock_subprocess.side_effect = Exception("Pandoc错误")
        
        result = call_tool("fetch_article", {"url": "http://example.com"})
        
        self.assertIn("转换失败: Pandoc错误", result)

    @unittest.mock.patch("linhai.tool.tools.http.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.tools.http.shutil.which")
    @unittest.mock.patch("linhai.tool.tools.http.subprocess.run")
    def test_fetch_article_table_attributes_removed(self, mock_subprocess, mock_which, mock_driver):
        """测试表格属性被正确删除"""
        # 模拟pandoc已安装
        mock_which.return_value = "/usr/bin/pandoc"
        
        # 模拟webdriver行为，包含带属性的表格
        mock_driver_instance = mock_driver.return_value.__enter__.return_value
        mock_driver_instance.page_source = """
        <html>
        <body>
            <table border="1" class="test-table" style="color: red;">
                <tr><th align="center">列1</th><th>列2</th></tr>
                <tr><td width="100">数据1</td><td>数据2</td></tr>
            </table>
        </body>
        </html>
        """
        
        # 模拟pandoc转换成功，输出应包含无属性的HTML表格
        with tempfile.NamedTemporaryFile(suffix=".md", mode='w', encoding='utf-8', delete=False) as tmp_md:
            tmp_md_path = tmp_md.name
            tmp_md.write("<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n")
            tmp_md.flush()
        
        mock_subprocess.return_value = None
        
        with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data="<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n")):
            result = call_tool("fetch_article", {"url": "http://example.com"})
        
        # 验证表格以HTML形式输出，但不应包含属性
        self.assertIn("<table>", result)
        self.assertIn("<tr>", result)
        self.assertIn("<th>列1</th>", result)
        self.assertIn("<td>数据1</td>", result)
        # 验证属性被删除
        self.assertNotIn("border", result)
        self.assertNotIn("class", result)
        self.assertNotIn("style", result)
        self.assertNotIn("align", result)
        self.assertNotIn("width", result)
        
        # 清理临时文件
        if os.path.exists(tmp_md_path):
            os.unlink(tmp_md_path)


if __name__ == "__main__":
    unittest.main()