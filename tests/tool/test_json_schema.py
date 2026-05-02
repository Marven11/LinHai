import unittest

from linhai.tool.base import (
    ToolSet,
    ToolArgInfo,
    _python_type_to_json_schema,
    to_tools_info,
)


class TestPythonTypeToJsonSchema(unittest.TestCase):
    def test_str(self):
        result = _python_type_to_json_schema("str")
        self.assertEqual(result, {"type": "string"})

    def test_int(self):
        result = _python_type_to_json_schema("int")
        self.assertEqual(result, {"type": "integer"})

    def test_bool(self):
        result = _python_type_to_json_schema("bool")
        self.assertEqual(result, {"type": "boolean"})

    def test_float(self):
        result = _python_type_to_json_schema("float")
        self.assertEqual(result, {"type": "number"})

    def test_list_str(self):
        result = _python_type_to_json_schema("list[str]")
        self.assertEqual(result, {"type": "array", "items": {"type": "string"}})

    def test_list_bare(self):
        result = _python_type_to_json_schema("list")
        self.assertEqual(result, {"type": "array"})

    def test_dict_str_any(self):
        result = _python_type_to_json_schema("Dict[str, Any]")
        self.assertEqual(result, {"type": "object"})

    def test_dict_str_str(self):
        result = _python_type_to_json_schema("Dict[str, str]")
        self.assertEqual(result, {"type": "object"})

    def test_optional_str(self):
        result = _python_type_to_json_schema("Optional[str]")
        self.assertEqual(result, {"type": "string"})

    def test_optional_int(self):
        result = _python_type_to_json_schema("Optional[int]")
        self.assertEqual(result, {"type": "integer"})

    def test_optional_bool(self):
        result = _python_type_to_json_schema("Optional[bool]")
        self.assertEqual(result, {"type": "boolean"})

    def test_optional_float(self):
        result = _python_type_to_json_schema("Optional[float]")
        self.assertEqual(result, {"type": "number"})

    def test_optional_dict(self):
        result = _python_type_to_json_schema("Optional[Dict[str, str]]")
        self.assertEqual(result, {"type": "object"})

    def test_optional_dict_any(self):
        result = _python_type_to_json_schema("Optional[Dict[str, Any]]")
        self.assertEqual(result, {"type": "object"})

    def test_optional_tuple(self):
        result = _python_type_to_json_schema("Optional[tuple[str, str]]")
        self.assertEqual(result, {"type": "array"})

    def test_tuple(self):
        result = _python_type_to_json_schema("tuple[str, str]")
        self.assertEqual(result, {"type": "array"})

    def test_union(self):
        result = _python_type_to_json_schema(
            "Optional[Dict[str, Union[str, int, float, bool]]]"
        )
        self.assertEqual(result, {"type": "object"})

    def test_dict_passthrough(self):
        schema = {"type": "string", "enum": ["a", "b"]}
        result = _python_type_to_json_schema(schema)
        self.assertEqual(result, schema)


class TestToToolsInfo(unittest.TestCase):
    def test_basic_tool_schema(self):
        toolset = ToolSet()

        @toolset.register_tool(
            name="read_file",
            desc="Read a file",
            args={
                "filepath": ToolArgInfo(desc="File path", type="str"),
                "show_lines": ToolArgInfo(desc="Show line numbers", type="bool"),
                "timeout": ToolArgInfo(desc="Timeout in seconds", type="int"),
                "ratio": ToolArgInfo(desc="Compression ratio", type="float"),
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
                "method": ToolArgInfo(desc="HTTP method", type="str"),
                "headers": ToolArgInfo(desc="Headers", type="Optional[Dict[str, str]]"),
                "argv": ToolArgInfo(desc="Arguments", type="list[str]"),
                "auth": ToolArgInfo(
                    desc="Auth tuple", type="Optional[tuple[str, str]]"
                ),
                "env": ToolArgInfo(desc="Environment", type="Optional[Dict[str, str]]"),
                "connection_args": ToolArgInfo(
                    desc="Connection args", type="Dict[str, Any]"
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
                "path": ToolArgInfo(desc="The file path to read", type="str"),
            },
            required_args=["path"],
        )
        def test_func(path: str):
            pass

        result = to_tools_info(toolset.get_tools())
        props = result[0]["function"]["parameters"]["properties"]
        self.assertEqual(props["path"]["description"], "The file path to read")
        self.assertEqual(props["path"]["type"], "string")


if __name__ == "__main__":
    unittest.main()
