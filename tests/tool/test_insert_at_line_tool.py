import unittest
import unittest.mock

from linhai.tool.base import ToolArgInfo
class TestInsertAtLineTool(unittest.TestCase):
    """Test cases for the insert_at_line tool."""

    def setUp(self):
        # 为每个测试创建新的ToolSet实例
        from linhai.tool.base import ToolSet

        self.toolset = ToolSet()
        # 使用register_tool装饰器注册insert_at_line工具
        from linhai.tool.tools.file import insert_at_line

        # 直接调用装饰器函数来注册现有工具
        self.toolset.register_tool(
            name="insert_at_line",
            desc="将内容插入到文件的指定行号位置",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "line_number": ToolArgInfo(desc="要插入的行号（从1开始）", type="int"),
                "content": ToolArgInfo(desc="要插入的内容", type="str"),
            },
            required_args=["filepath", "line_number", "content"],
        )(insert_at_line)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_success(self, mock_path):
        """测试成功插入内容到指定行"""
        # 模拟文件存在且是文件
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"

        # 调用工具
        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 2,
                "content": "inserted line",
                "expected_line_content": "line2",
            },
        )

        # 验证写入的内容
        mock_file.write_text.assert_called_once_with(
            "line1\ninserted line\nline2\nline3", encoding="utf-8"
        )
        self.assertIn("成功在文件", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_invalid_line_number(self, mock_path):
        """测试无效行号的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"

        # 行号太小
        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 0,
                "content": "inserted line",
                "expected_line_content": "dummy",
            },
        )
        self.assertIn("行号0无效", result)

        # 行号太大
        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 5,
                "content": "inserted line",
                "expected_line_content": "dummy",
            },
        )
        self.assertIn("行号5无效", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_file_not_exists(self, mock_path):
        """测试文件不存在的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = False

        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "nonexistent.txt",
                "line_number": 1,
                "content": "inserted line",
                "expected_line_content": "dummy",
            },
        )
        self.assertIn("文件路径", result)
        self.assertIn("不存在", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_not_file(self, mock_path):
        """测试路径不是文件的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = False

        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "directory/",
                "line_number": 1,
                "content": "inserted line",
                "expected_line_content": "dummy",
            },
        )
        self.assertIn("不是文件", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_line_content_match(self, mock_path):
        """测试预期行内容匹配时成功插入"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"

        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 2,
                "content": "inserted line",
                "expected_line_content": "line2",
            },
        )
        mock_file.write_text.assert_called_once_with(
            "line1\ninserted line\nline2\nline3", encoding="utf-8"
        )
        self.assertIn("成功在文件", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_line_content_mismatch(self, mock_path):
        """测试预期行内容不匹配时失败"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"

        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 2,
                "content": "inserted line",
                "expected_line_content": "wrong_line",
            },
        )
        self.assertIn("预期行内容不匹配", result)
        self.assertIn("实际内容为'line2'", result)
        self.assertIn("预期为'wrong_line'", result)
        mock_file.write_text.assert_not_called()

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_end_of_file(self, mock_path):
        """测试在文件末尾插入时预期内容为空的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"

        # 有效情况：预期内容为空
        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 4,
                "content": "inserted line",
                "expected_line_content": "",
            },
        )
        mock_file.write_text.assert_called_once_with(
            "line1\nline2\nline3\ninserted line\n", encoding="utf-8"
        )
        self.assertIn("成功在文件", result)

        # 无效情况：预期内容不为空
        mock_file.write_text.reset_mock()
        result = self.toolset.call_tool(
            "insert_at_line",
            {
                "filepath": "test.txt",
                "line_number": 4,
                "content": "inserted line",
                "expected_line_content": "not_empty",
            },
        )
        self.assertIn("预期行内容不匹配", result)
        self.assertIn("文件末尾应无内容", result)
        mock_file.write_text.assert_not_called()



