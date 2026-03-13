"""Unit tests for HTTP tools."""

import unittest
import unittest.mock
import tempfile
import os

from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.tool.general import fetch_article


class TestFetchArticleTool(unittest.TestCase):
    """Test cases for the fetch_article tool."""

    def setUp(self):
        self.toolset = ToolSet()
        self.toolset.register_tool(
            name="fetch_article",
            desc="抓取网页并转换为Markdown格式",
            args={
                "url": ToolArgInfo(desc="目标网页URL", type="str"),
                "http_downloader": ToolArgInfo(
                    desc="HTML下载器，可选值：'none'或'selenium'（默认使用selenium）或'httpx'",
                    type="str",
                ),
            },
            required_args=["url"],
        )(fetch_article)

    @unittest.mock.patch("linhai.tool.general.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    def test_fetch_article_success(self, mock_subprocess, mock_which, mock_driver):
        """测试fetch_article工具成功转换网页为Markdown"""
        mock_which.return_value = "/usr/bin/pandoc"

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

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as tmp_md:
            tmp_md_path = tmp_md.name
            tmp_md.write(
                "# 测试标题\n\n测试段落\n\n<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n\n![短URL图片](http://example.com/short.jpg)\n"
            )
            tmp_md.flush()

        mock_subprocess.return_value = None  # subprocess.run成功

        with unittest.mock.patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data="# 测试标题\n\n测试段落\n\n<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n\n![短URL图片](http://example.com/short.jpg)\n"
            ),
        ):
            result = self.toolset.call_tool(
                "fetch_article", {"url": "http://example.com"}
            )

        self.assertIn("测试标题", result)
        self.assertIn("测试段落", result)
        self.assertIn("<table>", result)
        self.assertIn("<tr>", result)
        self.assertIn("short.jpg", result)
        self.assertNotIn("a" * 800, result)
        self.assertNotIn("javascript:", result)

        if os.path.exists(tmp_md_path):
            os.unlink(tmp_md_path)

    def test_fetch_article_default_http_downloader(self):
        """测试fetch_article使用默认http_downloader（none）参数"""
        # 验证工具注册包含http_downloader参数
        tool_info = self.toolset.get_tools()["fetch_article"]
        # 工具信息结构可能包含'args'和'required_args'，但先检查键是否存在
        self.assertIn("args", tool_info)
        self.assertIn("http_downloader", tool_info["args"])
        self.assertEqual(
            tool_info["args"]["http_downloader"]["desc"],
            "HTML下载器，可选值：'none'或'selenium'（默认使用selenium）或'httpx'",
        )
        self.assertEqual(tool_info["args"]["http_downloader"]["type"], "str")
        # 验证参数是可选参数：如果存在'required_args'，则检查http_downloader不在其中
        if "required_args" in tool_info:
            self.assertNotIn("http_downloader", tool_info["required_args"])

    @unittest.mock.patch("linhai.tool.general._download_with_httpx")
    def test_fetch_article_httpx_downloader(self, mock_httpx_download):
        """测试fetch_article使用httpx下载器"""
        mock_httpx_download.return_value = "<html><body>Test content</body></html>"

        # 模拟pandoc已安装和其他依赖
        with unittest.mock.patch(
            "linhai.tool.general.shutil.which", return_value="/usr/bin/pandoc"
        ):
            with unittest.mock.patch("linhai.tool.general.subprocess.run"):
                with unittest.mock.patch(
                    "builtins.open", unittest.mock.mock_open(read_data="# Test")
                ):
                    # 测试调用工具时指定http_downloader='httpx'
                    result = self.toolset.call_tool(
                        "fetch_article",
                        {"url": "http://example.com", "http_downloader": "httpx"},
                    )
                    # 验证调用了httpx下载函数
                    mock_httpx_download.assert_called_once_with("http://example.com")
                    self.assertIn("Test", result)

    def test_fetch_article_invalid_http_downloader(self):
        """测试fetch_article使用无效的http_downloader参数"""
        # 测试调用工具时指定无效的http_downloader值
        result = self.toolset.call_tool(
            "fetch_article", {"url": "http://example.com", "http_downloader": "invalid"}
        )
        # 验证返回了正确的错误信息
        self.assertIn(
            "错误: http_downloader参数只能是'none'（默认selenium）、'selenium'或'httpx'，得到'invalid'",
            result,
        )

    @unittest.mock.patch("linhai.tool.general._download_with_selenium")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_article_pandoc_not_installed(self, mock_which, mock_download):
        """测试pandoc未安装的情况"""
        mock_which.return_value = None
        mock_download.return_value = "<html><body>Test</body></html>"

        result = self.toolset.call_tool("fetch_article", {"url": "http://example.com"})

        self.assertEqual(result, "错误：pandoc未安装，请先安装pandoc")

    @unittest.mock.patch("linhai.tool.general.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_article_webdriver_error(self, mock_which, mock_driver):
        """测试webdriver出错的情况"""
        mock_which.return_value = "/usr/bin/pandoc"

        mock_driver.side_effect = Exception("WebDriver错误")

        with self.assertRaises(Exception) as context:
            self.toolset.call_tool("fetch_article", {"url": "http://example.com"})
        self.assertIn("WebDriver错误", str(context.exception))

    @unittest.mock.patch("linhai.tool.general.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    def test_fetch_article_pandoc_error(self, mock_subprocess, mock_which, mock_driver):
        """测试pandoc转换出错的情况"""
        mock_which.return_value = "/usr/bin/pandoc"

        mock_driver_instance = mock_driver.return_value.__enter__.return_value
        mock_driver_instance.page_source = "<html><body>测试内容</body></html>"

        mock_subprocess.side_effect = Exception("Pandoc错误")

        with self.assertRaises(Exception) as context:
            self.toolset.call_tool("fetch_article", {"url": "http://example.com"})
        self.assertIn("Pandoc错误", str(context.exception))

    @unittest.mock.patch("linhai.tool.general.webdriver.Firefox")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    def test_fetch_article_table_attributes_removed(
        self, mock_subprocess, mock_which, mock_driver
    ):
        """测试表格属性被正确删除"""
        mock_which.return_value = "/usr/bin/pandoc"

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

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as tmp_md:
            tmp_md_path = tmp_md.name
            tmp_md.write(
                "<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n"
            )
            tmp_md.flush()

        mock_subprocess.return_value = None

        with unittest.mock.patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data="<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n"
            ),
        ):
            result = self.toolset.call_tool(
                "fetch_article", {"url": "http://example.com"}
            )

        self.assertIn("<table>", result)
        self.assertIn("<tr>", result)
        self.assertIn("<th>列1</th>", result)
        self.assertIn("<td>数据1</td>", result)
        self.assertNotIn("border", result)
        self.assertNotIn("class", result)
        self.assertNotIn("style", result)
        self.assertNotIn("align", result)
        self.assertNotIn("width", result)

        if os.path.exists(tmp_md_path):
            os.unlink(tmp_md_path)


if __name__ == "__main__":
    unittest.main()
