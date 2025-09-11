"""Unit tests for the tool module."""

import unittest
import unittest.mock

from linhai.llm import ToolCallMessage
from linhai.tool.base import (
    ToolArgInfo,
    call_tool,
    get_tools_info,
    register_tool,
    global_tools,
)
from linhai.tool.main import ToolManager


class TestToolManager(unittest.IsolatedAsyncioTestCase):
    """Test cases for the ToolManager class."""

    async def asyncSetUp(self):
        self.manager = ToolManager()

    async def test_successful_tool_call(self):
        """测试成功的工具调用"""
        mock_tool_call = ToolCallMessage(
            function_name="add_numbers", function_arguments={"a": 3, "b": 5}
        )

        # 模拟工具调用
        with unittest.mock.patch(
            "linhai.tool.main.call_tool", return_value=8
        ) as mock_call:
            result = await self.manager.process_tool_call(mock_tool_call)

            # 验证工具被正确调用
            mock_call.assert_called_once_with("add_numbers", {"a": 3, "b": 5})

            # 验证返回结果
            self.assertEqual(type(result).__name__, "ToolResultMessage")
            self.assertEqual(getattr(result, "content"), 8)

    async def test_failed_tool_call(self):
        """测试失败的工具调用"""
        mock_tool_call = ToolCallMessage(
            function_name="invalid_tool", function_arguments={}
        )

        # 模拟工具抛出异常
        with unittest.mock.patch(
            "linhai.tool.main.call_tool", side_effect=ValueError("Tool not found")
        ):
            result = await self.manager.process_tool_call(mock_tool_call)
            self.assertEqual(type(result).__name__, "ToolErrorMessage")
            self.assertEqual(getattr(result, "content"), "Tool not found")

    # 移除manager_run_loop测试，因为ToolManager不再有run方法


class TestToolFunctions(unittest.TestCase):
    """Test cases for tool functions."""

    def setUp(self):
        # 清空工具注册表
        global_tools.clear()

    def test_register_and_call_tool(self):
        """测试工具注册和调用"""

        # 注册测试工具
        @register_tool(
            name="add_numbers",
            desc="Add two numbers",
            args={
                "a": ToolArgInfo(desc="First number", type="int"),
                "b": ToolArgInfo(desc="Second number", type="int"),
            },
            required_args=["a", "b"],
        )
        def add_numbers(a, b):
            return a + b

        # 测试工具调用
        result = call_tool("add_numbers", {"a": 2, "b": 3})
        self.assertEqual(result, 5)

    def test_get_tools_info(self):
        """测试获取工具信息"""

        # 注册测试工具
        @register_tool(
            name="multiply_numbers",
            desc="Multiply two numbers",
            args={
                "x": ToolArgInfo(desc="First number", type="int"),
                "y": ToolArgInfo(desc="Second number", type="int"),
            },
            required_args=["x", "y"],
        )
        def multiply(x, y):
            return x * y

        # 获取工具信息
        tools_info = get_tools_info(global_tools)
        self.assertEqual(len(tools_info), 1)
        self.assertEqual(tools_info[0]["function"]["name"], "multiply_numbers")
        self.assertEqual(
            tools_info[0]["function"]["description"], "Multiply two numbers"
        )

    def test_tool_not_found(self):
        """测试工具不存在的情况"""
        with self.assertRaises(ValueError) as context:
            call_tool("nonexistent_tool", {})
        self.assertEqual(str(context.exception), "Tool not found: nonexistent_tool")


if __name__ == "__main__":
    unittest.main()


class TestInsertAtLineTool(unittest.TestCase):
    """Test cases for the insert_at_line tool."""

    def setUp(self):
        # 清空工具注册表
        global_tools.clear()
        # 注册insert_at_line工具
        from linhai.tool.tools.file import insert_at_line
        global_tools["insert_at_line"] = {
            "name": "insert_at_line",
            "func": insert_at_line,
            "desc": "将内容插入到文件的指定行号位置",
            "args": {
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "line_number": ToolArgInfo(desc="要插入的行号（从1开始）", type="int"),
                "content": ToolArgInfo(desc="要插入的内容", type="str"),
            },
            "required": ["filepath", "line_number", "content"],
        }

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_success(self, mock_path):
        """测试成功插入内容到指定行"""
        # 模拟文件存在且是文件
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"
        
        # 调用工具
        result = call_tool("insert_at_line", {
            "filepath": "test.txt",
            "line_number": 2,
            "content": "inserted line"
        })
        
        # 验证写入的内容
        mock_file.write_text.assert_called_once_with("line1\ninserted line\nline2\nline3", encoding="utf-8")
        self.assertIn("成功在文件", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_invalid_line_number(self, mock_path):
        """测试无效行号的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.read_text.return_value = "line1\nline2\nline3"
        
        # 行号太小
        result = call_tool("insert_at_line", {
            "filepath": "test.txt",
            "line_number": 0,
            "content": "inserted line"
        })
        self.assertIn("行号0无效", result)
        
        # 行号太大
        result = call_tool("insert_at_line", {
            "filepath": "test.txt",
            "line_number": 5,
            "content": "inserted line"
        })
        self.assertIn("行号5无效", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_file_not_exists(self, mock_path):
        """测试文件不存在的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = False
        
        result = call_tool("insert_at_line", {
            "filepath": "nonexistent.txt",
            "line_number": 1,
            "content": "inserted line"
        })
        self.assertIn("文件路径", result)
        self.assertIn("不存在", result)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    def test_insert_at_line_not_file(self, mock_path):
        """测试路径不是文件的情况"""
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = False
        
        result = call_tool("insert_at_line", {
            "filepath": "directory/",
            "line_number": 1,
            "content": "inserted line"
        })
        self.assertIn("不是文件", result)
