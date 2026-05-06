"""Unit tests for HTTP tools."""

import unittest
import unittest.mock
import tempfile
import os

from linhai.tool.base import ToolSet, ToolArgInfo, FailedToolResult
from linhai.tool.general import fetch_webpage


class TestFetchWebpageTool(unittest.TestCase):
    """Test cases for the fetch_webpage tool."""

    def setUp(self):
        self.toolset = ToolSet()
        self.toolset.register_tool(
            name="fetch_webpage",
            desc="抓取网页并转换为Markdown格式",
            args={
                "url": ToolArgInfo(desc="目标网页URL", type="str"),
                "http_downloader": ToolArgInfo(
                    desc="HTML下载器，必须指定'chromium'或'httpx'",
                    type="str",
                ),
            },
            required_args=["url", "http_downloader"],
        )(fetch_webpage)

    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_success(self, mock_which, mock_subprocess):
        """测试fetch_webpage工具成功转换网页为Markdown"""
        mock_which.side_effect = lambda x: (
            "/usr/bin/chromium" if x == "chromium" else "/usr/bin/pandoc"
        )
        html = """
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
        mock_subprocess.return_value = unittest.mock.Mock(
            returncode=0, stdout=html, stderr=""
        )

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as tmp_md:
            tmp_md_path = tmp_md.name
            tmp_md.write(
                "# 测试标题\n\n测试段落\n\n<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n\n![短URL图片](http://example.com/short.jpg)\n"
            )
            tmp_md.flush()

        with unittest.mock.patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data="# 测试标题\n\n测试段落\n\n<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n\n![短URL图片](http://example.com/short.jpg)\n"
            ),
        ):
            result = self.toolset.call_tool(
                "fetch_webpage",
                {"url": "http://example.com", "http_downloader": "chromium"},
            )

        self.assertIn("测试标题", result.content)
        self.assertIn("测试段落", result.content)
        self.assertIn("<table>", result.content)
        self.assertIn("<tr>", result.content)
        self.assertIn("short.jpg", result.content)
        self.assertNotIn("a" * 800, result.content)
        self.assertNotIn("javascript:", result.content)

        if os.path.exists(tmp_md_path):
            os.unlink(tmp_md_path)

    def test_fetch_webpage_required_http_downloader(self):
        """测试fetch_webpage的http_downloader为必填参数"""
        tools = self.toolset.get_tools()
        self.assertIn("fetch_webpage", tools)
        tool_info = tools["fetch_webpage"]
        self.assertIn("args", tool_info)
        self.assertIn("http_downloader", tool_info["args"])
        self.assertEqual(
            tool_info["args"]["http_downloader"]["desc"],
            "HTML下载器，必须指定'chromium'或'httpx'",
        )
        self.assertEqual(tool_info["args"]["http_downloader"]["type"], "str")
        self.assertIn("http_downloader", tool_info["required"])

    @unittest.mock.patch("linhai.tool.general._download_with_httpx")
    def test_fetch_webpage_httpx_downloader(self, mock_httpx_download):
        """测试fetch_webpage使用httpx下载器"""
        mock_httpx_download.return_value = "<html><body>Test content</body></html>"

        with unittest.mock.patch(
            "linhai.tool.general.shutil.which", return_value="/usr/bin/pandoc"
        ):
            with unittest.mock.patch("linhai.tool.general.subprocess.run"):
                with unittest.mock.patch(
                    "builtins.open", unittest.mock.mock_open(read_data="# Test")
                ):
                    result = self.toolset.call_tool(
                        "fetch_webpage",
                        {"url": "http://example.com", "http_downloader": "httpx"},
                    )
                    mock_httpx_download.assert_called_once_with("http://example.com")
                    self.assertIn("Test", result.content)

    def test_fetch_webpage_invalid_http_downloader(self):
        """测试fetch_webpage使用无效的http_downloader参数"""
        result = self.toolset.call_tool(
            "fetch_webpage", {"url": "http://example.com", "http_downloader": "invalid"}
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn(
            "错误: http_downloader参数只能是'chromium'或'httpx'，得到'invalid'",
            result.content,
        )

    @unittest.mock.patch("linhai.tool.general._download_with_chromium")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_pandoc_not_installed(self, mock_which, mock_download):
        """测试pandoc未安装的情况"""
        mock_which.side_effect = lambda x: (
            "/usr/bin/chromium" if x == "chromium" else None
        )
        mock_download.return_value = "<html><body>Test</body></html>"

        result = self.toolset.call_tool(
            "fetch_webpage",
            {"url": "http://example.com", "http_downloader": "chromium"},
        )

        self.assertIsInstance(result, FailedToolResult)
        self.assertEqual(result.content, "错误：pandoc未安装，请先安装pandoc")

    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_chromium_error(self, mock_which, mock_subprocess):
        """测试chromium出错的情况"""
        mock_which.return_value = "/usr/bin/chromium"
        mock_subprocess.return_value = unittest.mock.Mock(
            returncode=1, stdout="", stderr="chromium error"
        )

        with self.assertRaises(RuntimeError) as context:
            self.toolset.call_tool(
                "fetch_webpage",
                {"url": "http://example.com", "http_downloader": "chromium"},
            )
        self.assertIn("chromium下载失败", str(context.exception))

    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_pandoc_error(self, mock_which, mock_subprocess):
        """测试pandoc转换出错的情况"""
        mock_which.side_effect = lambda x: (
            "/usr/bin/chromium" if x == "chromium" else "/usr/bin/pandoc"
        )
        html = "<html><body>测试内容</body></html>"

        def side_effect(cmd, **kwargs):
            if cmd[0] == "/usr/bin/chromium":
                return unittest.mock.Mock(returncode=0, stdout=html, stderr="")
            raise Exception("Pandoc错误")

        mock_subprocess.side_effect = side_effect

        with self.assertRaises(Exception) as context:
            self.toolset.call_tool(
                "fetch_webpage",
                {"url": "http://example.com", "http_downloader": "chromium"},
            )
        self.assertIn("Pandoc错误", str(context.exception))

    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_table_attributes_removed(self, mock_which, mock_subprocess):
        """测试表格属性被正确删除"""
        mock_which.side_effect = lambda x: (
            "/usr/bin/chromium" if x == "chromium" else "/usr/bin/pandoc"
        )
        html = """
        <html>
        <body>
            <table border="1" class="test-table" style="color: red;">
                <tr><th align="center">列1</th><th>列2</th></tr>
                <tr><td width="100">数据1</td><td>数据2</td></tr>
            </table>
        </body>
        </html>
        """
        mock_subprocess.return_value = unittest.mock.Mock(
            returncode=0, stdout=html, stderr=""
        )

        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", encoding="utf-8", delete=False
        ) as tmp_md:
            tmp_md_path = tmp_md.name
            tmp_md.write(
                "<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n"
            )
            tmp_md.flush()

        mock_subprocess.return_value = unittest.mock.Mock(
            returncode=0, stdout=html, stderr=""
        )

        with unittest.mock.patch(
            "builtins.open",
            unittest.mock.mock_open(
                read_data="<table>\n<tr><th>列1</th><th>列2</th></tr>\n<tr><td>数据1</td><td>数据2</td></tr>\n</table>\n"
            ),
        ):
            result = self.toolset.call_tool(
                "fetch_webpage",
                {"url": "http://example.com", "http_downloader": "chromium"},
            )

        self.assertIn("<table>", result.content)
        self.assertIn("<tr>", result.content)
        self.assertIn("<th>列1</th>", result.content)
        self.assertIn("<td>数据1</td>", result.content)
        self.assertNotIn("border", result.content)
        self.assertNotIn("class", result.content)
        self.assertNotIn("style", result.content)
        self.assertNotIn("align", result.content)
        self.assertNotIn("width", result.content)

        if os.path.exists(tmp_md_path):
            os.unlink(tmp_md_path)

    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_chromium_not_installed(self, mock_which):
        """测试chrome/chromium未安装的情况"""
        mock_which.return_value = None

        with self.assertRaises(RuntimeError) as context:
            self.toolset.call_tool(
                "fetch_webpage",
                {"url": "http://example.com", "http_downloader": "chromium"},
            )
        self.assertIn("chrome/chromium未安装", str(context.exception))

    @unittest.mock.patch("linhai.tool.general.subprocess.run")
    @unittest.mock.patch("linhai.tool.general.shutil.which")
    def test_fetch_webpage_fallback_to_chrome(self, mock_which, mock_subprocess):
        """测试chromium不存在时fallback到chrome"""
        mock_which.side_effect = lambda x: (
            "/usr/bin/google-chrome-stable"
            if x == "google-chrome-stable"
            else "/usr/bin/pandoc" if x == "pandoc" else None
        )
        html = "<html><body>Test</body></html>"
        mock_subprocess.return_value = unittest.mock.Mock(
            returncode=0, stdout=html, stderr=""
        )

        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data="# Test")
        ):
            result = self.toolset.call_tool(
                "fetch_webpage",
                {"url": "http://example.com", "http_downloader": "chromium"},
            )
        self.assertIn("Test", result.content)


if __name__ == "__main__":
    unittest.main()
