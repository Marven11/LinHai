import unittest

import jsonschema

from linhai.tool.base import (
    ToolSet,
    ToolArgInfo,
    to_tools_info,
)


class TestSchemaValidationInRegisterTool(unittest.TestCase):
    def test_valid_schema_accepted(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="test_valid",
            desc="test",
            args={
                "x": ToolArgInfo(desc="x", schema={"type": "string"}),
            },
            required_args=["x"],
        )
        def test_valid(x: str):
            pass

        self.assertTrue(toolset.has_tool("test_valid"))

    def test_invalid_schema_rejected(self):
        toolset = ToolSet()
        with self.assertRaises(jsonschema.exceptions.SchemaError):

            @toolset.register_tool(
                name="test_invalid",
                desc="test",
                args={
                    "x": ToolArgInfo(desc="x", schema={"type": "not_a_real_type"}),
                },
                required_args=["x"],
            )
            def test_invalid(x):
                pass

    def test_complex_valid_schema_accepted(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="test_complex",
            desc="test",
            args={
                "items": ToolArgInfo(
                    desc="list of items",
                    schema={
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "number"},
                            },
                            "required": ["name"],
                        },
                    },
                ),
                "mode": ToolArgInfo(
                    desc="processing mode",
                    schema={"type": "string", "enum": ["fast", "slow"]},
                ),
            },
            required_args=["items"],
        )
        def test_complex(items, mode="fast"):
            pass

        self.assertTrue(toolset.has_tool("test_complex"))


class TestToToolsInfo(unittest.TestCase):
    def test_basic_tool_schema(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="read_file",
            desc="Read a file",
            args={
                "filepath": ToolArgInfo(desc="File path", schema={"type": "string"}),
                "show_lines": ToolArgInfo(
                    desc="Show line numbers", schema={"type": "boolean"}
                ),
                "timeout": ToolArgInfo(
                    desc="Timeout in seconds", schema={"type": "integer"}
                ),
                "ratio": ToolArgInfo(
                    desc="Compression ratio", schema={"type": "number"}
                ),
            },
            required_args=["filepath"],
        )
        def read_file(
            filepath: str,
            show_lines: bool = False,
            timeout: int = 60,
            ratio: float = 0.0,
        ):
            pass

        result = to_tools_info(toolset.get_tools())
        self.assertEqual(len(result), 1)

        tool_info = result[0]
        self.assertEqual(tool_info["type"], "function")
        self.assertEqual(tool_info["function"]["name"], "read_file")

        props = tool_info["function"]["parameters"]["properties"]
        self.assertEqual(props["filepath"]["type"], "string")
        self.assertEqual(props["show_lines"]["type"], "boolean")
        self.assertEqual(props["timeout"]["type"], "integer")
        self.assertEqual(props["ratio"]["type"], "number")

        self.assertEqual(tool_info["function"]["parameters"]["required"], ["filepath"])

    def test_complex_types(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="http_request",
            desc="Send HTTP request",
            args={
                "method": ToolArgInfo(desc="HTTP method", schema={"type": "string"}),
                "headers": ToolArgInfo(desc="Headers", schema={"type": "object"}),
                "argv": ToolArgInfo(
                    desc="Arguments",
                    schema={"type": "array", "items": {"type": "string"}},
                ),
                "auth": ToolArgInfo(
                    desc="Auth tuple",
                    schema={"type": "array", "items": {"type": "string"}},
                ),
                "env": ToolArgInfo(desc="Environment", schema={"type": "object"}),
                "connection_args": ToolArgInfo(
                    desc="Connection args", schema={"type": "object"}
                ),
            },
            required_args=["method"],
        )
        def http_request(method: str, **kwargs):
            pass

        result = to_tools_info(toolset.get_tools())
        props = result[0]["function"]["parameters"]["properties"]

        self.assertEqual(props["method"]["type"], "string")
        self.assertEqual(props["headers"]["type"], "object")
        self.assertEqual(props["argv"]["type"], "array")
        self.assertEqual(props["argv"].get("items"), {"type": "string"})
        self.assertEqual(props["auth"]["type"], "array")
        self.assertEqual(props["env"]["type"], "object")
        self.assertEqual(props["connection_args"]["type"], "object")

    def test_empty_args(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="list_machines",
            desc="List machines",
            args={},
            required_args=[],
        )
        def list_machines():
            pass

        result = to_tools_info(toolset.get_tools())
        self.assertEqual(len(result), 1)
        props = result[0]["function"]["parameters"]["properties"]
        self.assertEqual(props, {})

    def test_description_preserved(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="test",
            desc="A test tool",
            args={
                "path": ToolArgInfo(
                    desc="The file path to read", schema={"type": "string"}
                ),
            },
            required_args=["path"],
        )
        def test_func(path: str):
            pass

        result = to_tools_info(toolset.get_tools())
        props = result[0]["function"]["parameters"]["properties"]
        self.assertEqual(props["path"]["description"], "The file path to read")
        self.assertEqual(props["path"]["type"], "string")

    def test_enum_constraint_preserved(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="test_enum",
            desc="test",
            args={
                "mode": ToolArgInfo(
                    desc="mode",
                    schema={"type": "string", "enum": ["a", "b", "c"]},
                ),
            },
            required_args=["mode"],
        )
        def test_enum(mode: str):
            pass

        result = to_tools_info(toolset.get_tools())
        props = result[0]["function"]["parameters"]["properties"]
        self.assertEqual(props["mode"]["type"], "string")
        self.assertEqual(props["mode"]["enum"], ["a", "b", "c"])


class TestToolArgumentValidation(unittest.IsolatedAsyncioTestCase):
    def _make_toolset(self) -> ToolSet:
        toolset = ToolSet()

        @toolset.register_tool(
            name="test_tool",
            desc="test",
            args={
                "name": ToolArgInfo(desc="name", schema={"type": "string"}),
                "count": ToolArgInfo(desc="count", schema={"type": "integer"}),
                "tags": ToolArgInfo(
                    desc="tags",
                    schema={"type": "array", "items": {"type": "string"}},
                ),
            },
            required_args=["name"],
        )
        def test_tool(name: str, count: int = 0, tags=None):
            return name

        return toolset

    async def test_valid_arguments_pass(self):
        from linhai.tool.main import ToolManager

        toolset = self._make_toolset()
        tool_def = toolset.get_tools()["test_tool"]
        from linhai.registry import Registry
        from linhai.config import ToolConfig

        registry = Registry()
        manager = ToolManager(
            registry=registry, config=ToolConfig(), mcp_connector=None
        )
        errors = manager._validate_tool_arguments(
            tool_def, {"name": "hello", "count": 5, "tags": ["a", "b"]}
        )
        self.assertEqual(errors, [])

    async def test_missing_required_argument(self):
        from linhai.tool.main import ToolManager
        from linhai.registry import Registry
        from linhai.config import ToolConfig

        toolset = self._make_toolset()
        tool_def = toolset.get_tools()["test_tool"]
        registry = Registry()
        manager = ToolManager(
            registry=registry, config=ToolConfig(), mcp_connector=None
        )
        errors = manager._validate_tool_arguments(tool_def, {"count": 5})
        self.assertTrue(len(errors) > 0)
        self.assertTrue(
            any("required" in e.lower() or "name" in e.lower() for e in errors)
        )

    async def test_wrong_type_argument(self):
        from linhai.tool.main import ToolManager
        from linhai.registry import Registry
        from linhai.config import ToolConfig

        toolset = self._make_toolset()
        tool_def = toolset.get_tools()["test_tool"]
        registry = Registry()
        manager = ToolManager(
            registry=registry, config=ToolConfig(), mcp_connector=None
        )
        errors = manager._validate_tool_arguments(
            tool_def, {"name": "hello", "count": "not_an_int"}
        )
        self.assertTrue(len(errors) > 0)

    async def test_extra_argument_ignored(self):
        from linhai.tool.main import ToolManager
        from linhai.registry import Registry
        from linhai.config import ToolConfig

        toolset = self._make_toolset()
        tool_def = toolset.get_tools()["test_tool"]
        registry = Registry()
        manager = ToolManager(
            registry=registry, config=ToolConfig(), mcp_connector=None
        )
        errors = manager._validate_tool_arguments(
            tool_def, {"name": "hello", "extra_param": 123}
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
