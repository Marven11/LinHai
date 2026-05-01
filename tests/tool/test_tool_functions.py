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
                "a": ToolArgInfo(desc="First number", type="int"),
                "b": ToolArgInfo(desc="Second number", type="int"),
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
                "x": ToolArgInfo(desc="First number", type="int"),
                "y": ToolArgInfo(desc="Second number", type="int"),
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

    def test_to_tools_info_python_type_mapping(self):
        """测试Python类型名映射到JSON Schema类型名"""

        @self.toolset.register_tool(
            name="type_test",
            desc="Test type mapping",
            args={
                "name": ToolArgInfo(desc="A string", type="str"),
                "count": ToolArgInfo(desc="An integer", type="int"),
                "ratio": ToolArgInfo(desc="A float", type="float"),
                "flag": ToolArgInfo(desc="A bool", type="bool"),
            },
            required_args=["name"],
        )
        def type_test(name, count=0, ratio=0.0, flag=False):
            return name

        from linhai.tool.base import to_tools_info

        tools_info = to_tools_info(self.toolset.get_tools())
        props = tools_info[0]["function"]["parameters"]["properties"]
        self.assertEqual(props["name"]["type"], "string")
        self.assertEqual(props["count"]["type"], "integer")
        self.assertEqual(props["ratio"]["type"], "number")
        self.assertEqual(props["flag"]["type"], "boolean")

    def test_to_tools_info_dict_type_expansion(self):
        """测试dict类型展开merge到property定义"""

        @self.toolset.register_tool(
            name="dict_type_test",
            desc="Test dict type",
            args={
                "args": ToolArgInfo(
                    desc="An object arg",
                    type={"type": "object", "properties": {"key": {"type": "string"}}},
                ),
            },
            required_args=["args"],
        )
        def dict_type_test(args):
            return args

        from linhai.tool.base import to_tools_info

        tools_info = to_tools_info(self.toolset.get_tools())
        prop = tools_info[0]["function"]["parameters"]["properties"]["args"]
        self.assertEqual(prop["type"], "object")
        self.assertIn("key", prop["properties"])
        self.assertNotIsInstance(prop["type"], dict)

    def test_tool_not_found(self):
        """测试工具不存在的情况"""
        with self.assertRaises(ValueError) as context:
            utils_tools.call_tool("nonexistent_tool", {})
        self.assertEqual(str(context.exception), "Tool not found: nonexistent_tool")
