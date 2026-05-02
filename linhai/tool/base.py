from typing import (
    TypedDict,
    Callable,
    Any,
    Awaitable,
    Protocol,
    runtime_checkable,
    Union,
    get_origin,
    get_args,
)

import json
import tempfile
import reprlib
import hashlib
from pathlib import Path

from pydantic import BaseModel

from linhai.type_hints import (
    LanguageModelMessage,
    ChatCompletionContentPartTextParam,
    ChatCompletionContentPartImageParam,
)
from linhai.base import Message, register_message
import linhai


class ToolArgInfo(TypedDict):
    desc: str
    type: str | dict[str, Any]


class Tool(TypedDict):
    name: str
    desc: str
    args: dict[str, ToolArgInfo]
    required: list[str]
    func: Callable[..., "ToolResult | Awaitable[ToolResult]"]


_TYPE_EVAL_GLOBALS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "Dict": dict,
    "Optional": Union,
    "Union": Union,
    "tuple": tuple,
    "Tuple": tuple,
    "Any": Any,
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}

_PYTHON_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    bool: "boolean",
    float: "number",
}


def _python_type_to_json_schema(python_type: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(python_type, dict):
        return python_type

    type_obj = eval(python_type, _TYPE_EVAL_GLOBALS, {})
    return _type_obj_to_schema(type_obj)


def _type_obj_to_schema(type_obj: type) -> dict[str, Any]:
    if type_obj is list:
        return {"type": "array"}
    if type_obj is dict:
        return {"type": "object"}
    if type_obj is tuple:
        return {"type": "array"}

    origin = get_origin(type_obj)

    if origin is Union:
        args = get_args(type_obj)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _type_obj_to_schema(non_none[0])
        return {"type": "string"}

    if origin is list:
        args = get_args(type_obj)
        if args:
            return {"type": "array", "items": _type_obj_to_schema(args[0])}
        return {"type": "array"}

    if origin is dict:
        return {"type": "object"}

    if origin is tuple:
        return {"type": "array"}

    mapped = _PYTHON_TYPE_TO_JSON.get(type_obj)
    if mapped:
        return {"type": mapped}

    return {"type": "string"}


def to_tools_info(tools: dict[str, Tool]) -> list[dict]:
    tool_info_list = []
    for tool in tools.values():
        properties: dict[str, Any] = {}
        parameters = {
            "type": "object",
            "properties": properties,
            "required": tool["required"],
        }

        for arg_name, arg_info in tool["args"].items():
            schema = _python_type_to_json_schema(arg_info["type"])
            schema["description"] = arg_info["desc"]
            properties[arg_name] = schema

        tool_info = {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["desc"],
                "parameters": parameters,
            },
        }
        tool_info_list.append(tool_info)

    return tool_info_list


class ToolSet:
    def __init__(self):
        self.tools: dict[str, Tool] = {}

    def register_tool(
        self,
        name: str,
        desc: str,
        args: dict[str, ToolArgInfo],
        required_args: list[str],
    ):

        def _wraps(
            f: Callable[..., "ToolResult | Awaitable[ToolResult]"],
        ) -> Callable[..., "ToolResult | Awaitable[ToolResult]"]:
            self.tools[name] = {
                "name": name,
                "func": f,
                "desc": desc,
                "args": args,
                "required": required_args,
            }
            return f

        return _wraps

    def get_tool(
        self, name: str
    ) -> Callable[..., "ToolResult | Awaitable[ToolResult]"]:
        if name not in self.tools:
            raise ValueError(f"Tool not found: {name}")
        return self.tools[name]["func"]

    def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        return self.get_tool(name)(**args)

    def get_tools(self):
        return self.tools

    def has_tool(self, name: str):
        return name in self.tools

    def add_toolset(self, toolset: "ToolSet") -> None:
        for tool_name, tool in toolset.tools.items():
            if tool_name in self.tools:
                raise ValueError(f"Tool {tool_name} already exists in this ToolSet")
            self.tools[tool_name] = tool


ToolResultContent = (
    str | list[ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam]
)


TOOL_RESULT_REGISTRY: dict[str, type] = {}


def register_tool_result(cls):
    TOOL_RESULT_REGISTRY[cls.__name__] = cls
    return cls


def tool_result_from_json(json_str: str) -> "ToolResult":
    data = json.loads(json_str)
    type_name = data.get("type")
    cls = TOOL_RESULT_REGISTRY.get(type_name)
    if cls is None:
        raise RuntimeError(f"Unknown ToolResult type: {type_name}")
    return cls.from_json(json_str)


@runtime_checkable
class ToolResult(Protocol):
    def to_llm_content(self) -> ToolResultContent:
        raise NotImplementedError()

    def to_json(self) -> str:
        raise NotImplementedError()

    @classmethod
    def from_json(cls, json_str: str) -> "ToolResult":
        raise NotImplementedError()


@register_tool_result
class SuccessfulToolResult(BaseModel):
    content: str

    def to_llm_content(self) -> str:
        return self.content

    def to_json(self) -> str:
        return json.dumps({"type": "SuccessfulToolResult", "content": self.content})

    @classmethod
    def from_json(cls, json_str: str) -> "SuccessfulToolResult":
        data = json.loads(json_str)
        return cls(content=data["content"])


@register_tool_result
class FailedToolResult(BaseModel):
    content: str

    def to_llm_content(self) -> str:
        return self.content

    def to_json(self) -> str:
        return json.dumps({"type": "FailedToolResult", "content": self.content})

    @classmethod
    def from_json(cls, json_str: str) -> "FailedToolResult":
        data = json.loads(json_str)
        return cls(content=data["content"])


@register_tool_result
class FileContentToolResult(BaseModel):
    filepath: str
    content: str
    show_line_numbers: bool

    def to_llm_content(self) -> str:
        if self.show_line_numbers:
            lines = self.content.splitlines()
            numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
            formatted_content = "\n".join(numbered_lines)
        else:
            formatted_content = self.content
        return (
            "<<file_content>>\n<<message>>"
            "以下是文件的完整内容，不要重复读取！<<message>>"
            f"<<filepath>>{self.filepath!r}<<filepath>>\n"
            f"<<content>>{formatted_content}<<content>>\n"
            "<<file_content>>"
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": "FileContentToolResult",
                "filepath": self.filepath,
                "content": self.content,
                "show_line_numbers": self.show_line_numbers,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "FileContentToolResult":
        data = json.loads(json_str)
        return cls(
            filepath=data["filepath"],
            content=data["content"],
            show_line_numbers=data["show_line_numbers"],
        )

    def __eq__(self, other) -> bool:
        if not isinstance(other, FileContentToolResult):
            return False
        return (
            self.content == other.content
            and Path(self.filepath).resolve() == Path(other.filepath).resolve()
            and self.show_line_numbers == other.show_line_numbers
        )

    def __hash__(self) -> int:
        return hash((Path(self.filepath).resolve(), hash(self.content)))


@register_tool_result
class ImageToolResult(BaseModel):
    image_bytes_b64: str
    mime_type: str
    filename: str | None
    quality: str
    width: int
    height: int

    def to_llm_content(
        self,
    ) -> list[ChatCompletionContentPartTextParam | ChatCompletionContentPartImageParam]:
        return [
            ChatCompletionContentPartImageParam(
                type="image_url",
                image_url={
                    "url": f"data:{self.mime_type};base64,{self.image_bytes_b64}"
                },
            )
        ]

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": "ImageToolResult",
                "image_bytes_b64": self.image_bytes_b64,
                "mime_type": self.mime_type,
                "filename": self.filename,
                "quality": self.quality,
                "width": self.width,
                "height": self.height,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ImageToolResult":
        data = json.loads(json_str)
        return cls(
            image_bytes_b64=data["image_bytes_b64"],
            mime_type=data["mime_type"],
            filename=data.get("filename"),
            quality=data.get("quality", "raw"),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )


def _get_file_content_info(result: ToolResult) -> str | None:
    if isinstance(result, FileContentToolResult):
        return result.content
    llm_content = result.to_llm_content()
    if isinstance(llm_content, str):
        return llm_content
    return None


@register_message
class ToolCallResultMessage(Message):

    def __init__(
        self,
        tool_name: str,
        tool_index: int,
        result: ToolResult,
        toolcall_arguments: dict,
    ):
        self.tool_name = tool_name
        self.tool_index = tool_index
        self.result = result
        self.toolcall_arguments = toolcall_arguments

    def to_llm_message(self) -> LanguageModelMessage:
        llm_content = self.result.to_llm_content()
        if isinstance(llm_content, list):
            content_parts = []
            if isinstance(self.result, FailedToolResult):
                status = (
                    "错误：工具执行失败，你需要缓慢且仔细地反思并总结："
                    "1. 失败的原因 2. 用户的需求 3. 你弄错了什么"
                    " 4. 如何正确完成用户的需求 5. 如何避免工具失败"
                )
            else:
                status = "工具执行成功"
            prefix_parts = [
                "<<tool>>",
                f"<<name>>{self.tool_name}<<name>>",
                f"<<index>>{self.tool_index}<<index>>",
            ]
            if isinstance(self.result, FailedToolResult) and self.toolcall_arguments:
                r = reprlib.Repr()
                r.maxstring = 100
                argument_repr = r.repr(self.toolcall_arguments)
                prefix_parts.append(
                    f"<<toolcall_argument>>{argument_repr}<<toolcall_argument>>"
                )
            prefix_parts.append(f"<<message>>{status}<<message>>")
            content_parts.append({"type": "text", "text": "\n".join(prefix_parts)})
            content_parts.extend(llm_content)
            content_parts.append({"type": "text", "text": "<<tool>>"})
            return {"role": "user", "content": content_parts}
        else:
            return {"role": "user", "content": self.get_content()}

    def get_content(self) -> str:
        if isinstance(self.result, FailedToolResult):
            status = (
                "错误：工具执行失败，你需要缓慢且仔细地反思并总结："
                "1. 失败的原因 2. 用户的需求 3. 你弄错了什么"
                " 4. 如何正确完成用户的需求 5. 如何避免工具失败"
            )
        else:
            status = "工具执行成功"

        content_parts = [
            "<<tool>>",
            f"<<name>>{self.tool_name}<<name>>",
            f"<<index>>{self.tool_index}<<index>>",
        ]
        if isinstance(self.result, FailedToolResult) and self.toolcall_arguments:
            r = reprlib.Repr()
            r.maxstring = 100
            argument_repr = r.repr(self.toolcall_arguments)
            content_parts.append(
                f"<<toolcall_argument>>{argument_repr}<<toolcall_argument>>"
            )
        llm_content = self.result.to_llm_content()
        content_str = llm_content if isinstance(llm_content, str) else str(llm_content)
        if isinstance(self.result, FailedToolResult):
            data_or_error = f"<<error>>{content_str}<<error>>"
        else:
            data_or_error = f"<<data>>{content_str}<<data>>"
        content_parts.extend(
            [
                f"<<message>>{status}<<message>>",
                data_or_error,
                "<<tool>>",
            ]
        )
        return "\n".join(content_parts)

    def to_json(self) -> str:
        data = {
            "tool_name": self.tool_name,
            "tool_index": self.tool_index,
            "result": self.result.to_json(),
            "toolcall_arguments": self.toolcall_arguments,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, registry: "linhai.registry.Registry"):
        data = json.loads(json_str)
        result = tool_result_from_json(data["result"])
        return cls(
            tool_name=data["tool_name"],
            tool_index=data["tool_index"],
            result=result,
            toolcall_arguments=data.get("toolcall_arguments", {}),
        )


utils_tools = ToolSet()
