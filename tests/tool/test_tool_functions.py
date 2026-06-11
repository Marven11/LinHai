"""Unit tests for tool functions."""

import unittest

from linhai.tool.base import ToolArgInfo, utils_tools


class TestToolFunctions(unittest.TestCase):
    """Test cases for tool functions."""

    def setUp(self):
        from linhai.tool.base import ToolSet

        self.toolset = ToolSet()

    def test_register_and_call_tool(self):
        """测试工具注册和调用"""

        @self.toolset.register_tool(
            name="add_numbers",
            desc="Add two numbers",
            args={
                "a": ToolArgInfo(desc="First number", schema={"type": "integer"}),
                "b": ToolArgInfo(desc="Second number", schema={"type": "integer"}),
            },
            required_args=["a", "b"],
        )
        def add_numbers(a, b):
            return a + b

        result = self.toolset.call_tool("add_numbers", {"a": 2, "b": 3})
        self.assertEqual(result, 5)

    def test_get_tools_info(self):
        """测试获取工具信息"""

        @self.toolset.register_tool(
            name="multiply_numbers",
            desc="Multiply two numbers",
            args={
                "x": ToolArgInfo(desc="First number", schema={"type": "integer"}),
                "y": ToolArgInfo(desc="Second number", schema={"type": "integer"}),
            },
            required_args=["x", "y"],
        )
        def multiply(x, y):
            return x * y

        from linhai.tool.base import to_tools_info

        tools_info = to_tools_info(self.toolset.get_tools())
        self.assertEqual(len(tools_info), 1)
        self.assertEqual(tools_info[0]["function"]["name"], "multiply_numbers")
        self.assertEqual(
            tools_info[0]["function"]["description"], "Multiply two numbers"
        )

    def test_tool_not_found(self):
        """测试工具不存在的情况"""
        with self.assertRaises(ValueError) as context:
            utils_tools.call_tool("nonexistent_tool", {})
        self.assertEqual(str(context.exception), "Tool not found: nonexistent_tool")
