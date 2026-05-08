"""Markdown解析模块，用于从Markdown文本中提取JSON代码块和工具调用。"""

import json
from reprlib import Repr
from typing import Any, List, Tuple
from linhai.type_hints import ToolCallDict
import mistune

repr_obj = Repr()
repr_obj.maxstring = 50


class CodeBlockRenderer(mistune.HTMLRenderer):
    """自定义渲染器用于提取JSON工具调用的代码块"""

    def __init__(self):
        super().__init__()
        self.code_blocks = []

    def block_code(self, code, info=None):
        """重写代码块渲染方法"""
        language = info.strip() if info else "plaintext"
        self.code_blocks.append({"language": language, "content": code})
        return super().block_code(code, info)


def check_jsonl(tool_call: str):
    """检查（错误的）工具调用是否是jsonl，有时agent(kimi k2.5)会在一个code block中输出多个json"""
    if tool_call.count("\n") == 0:
        return False
    try:
        _ = [
            json.loads(line.strip()) for line in tool_call.splitlines() if line.strip()
        ]
        return True
    except json.JSONDecodeError:
        return False


def extract_json_blocks(markdown_text: str) -> List[Any]:
    """
    从Markdown文本中提取所有JSON代码块

    Args:
        markdown_text: 要解析的Markdown文本

    Returns:
        包含所有JSON代码块内容的列表，每个元素是解析后的数据
    """
    renderer = CodeBlockRenderer()
    markdown = mistune.create_markdown(renderer=renderer)
    markdown(markdown_text)

    json_blocks = []
    for block in renderer.code_blocks:
        if block["language"].lower() == "json":
            data = json.loads(block["content"])
            json_blocks.append(data)
    return json_blocks


def extract_tool_calls(markdown_text: str) -> List[ToolCallDict]:
    """
    从Markdown文本中提取JSON格式的工具调用

    Args:
        markdown_text: 要解析的Markdown文本

    Returns:
        包含工具调用信息的列表，每个元素是包含'name'和'arguments'的字典
    """
    tool_calls, _ = extract_tool_calls_with_errors(markdown_text)
    return tool_calls


def _extract_json_error_context(error: json.JSONDecodeError, content: str) -> str:
    error_line, error_col = error.lineno, error.colno
    content_lines = content.split("\n")
    start_line, end_line = max(0, error_line - 2), min(
        len(content_lines), error_line + 2
    )

    context_with_marker = [line for line in content_lines[start_line:end_line]]
    if error_line <= end_line:
        marker = (
            " " * (error_col - 1) + "^" + f" (line {error_line}, column {error_col})"
        )
        context_with_marker.insert(error_line - start_line + 1, marker)

    return "\n".join(context_with_marker)


def extract_tool_calls_with_errors(
    markdown_text: str, language: str = "json toolcall"
) -> Tuple[List[ToolCallDict], List[str]]:
    """
    从Markdown文本中提取JSON格式的工具调用，并返回错误消息列表

    Args:
        markdown_text: 要解析的Markdown文本
        language: 要提取的代码块语言，默认为"json toolcall"

    Returns:
        tuple[list[dict], list[str]]: 工具调用列表和错误消息列表
    """
    renderer = CodeBlockRenderer()
    markdown = mistune.create_markdown(renderer=renderer)
    markdown(markdown_text)

    tool_calls: list[ToolCallDict] = []
    errors: list[str] = []

    for i, block in enumerate(renderer.code_blocks):
        if block["language"].lower() == language.lower():
            try:
                data = json.loads(block["content"].strip())

                if not isinstance(data, dict):
                    errors.append(
                        f"工具调用解析出错：第{i+1}个code block中的JSON不是对象类型，"
                        f"实际类型: {type(data).__name__}\n"
                        f"内容: {repr_obj.repr(block['content'])}"
                    )
                    continue

                if "name" not in data:
                    errors.append(
                        f"工具调用解析出错：第{i+1}个code block缺少必需的'name'字段\n"
                        f"内容: {repr_obj.repr(block['content'])}"
                    )
                    continue

                if "arguments" not in data:
                    errors.append(
                        f"工具调用解析出错：第{i+1}个code block缺少必需的'arguments'字段\n"
                        f"内容: {repr_obj.repr(block['content'])}"
                    )
                    continue

                if not isinstance(data["arguments"], dict):
                    errors.append(
                        f"工具调用解析出错：第{i+1}个code block中的'arguments'字段不是字典类型，"
                        f"实际类型: {type(data['arguments']).__name__}\n"
                        f"内容: {repr_obj.repr(block['content'])}"
                    )
                    continue

                tc: ToolCallDict = {
                    "name": data["name"],
                    "arguments": data["arguments"],
                }
                if "assert_success" in data:
                    tc["assert_success"] = data["assert_success"]
                if "with_secret" in data:
                    tc["with_secret"] = data["with_secret"]
                tool_calls.append(tc)
            except json.JSONDecodeError as e:
                context_str = _extract_json_error_context(e, block["content"])
                error_message = (
                    f"工具调用解析出错：第{i+1}个code block中的JSON格式无效: {str(e)}\n"
                    f"错误位置: 第{e.lineno}行, 第{e.colno}列\n"
                    f"错误附近内容:\n{context_str}\n"
                )
                if check_jsonl(block["content"]):
                    error_message += (
                        "在一个code block中发现了多个json数据，你是不是在一个code block中输出了多个json object了？\n"
                        """
多工具调用的正确格式是:

```json toolcall
{"name": "toolcall1", "arguments": {...}}
```

```json toolcall
{"name": "toolcall2", "arguments": {...}}
```

而不是:

```json toolcall
{"name": "toolcall1", "arguments": {...}}
{"name": "toolcall2", "arguments": {...}}
```
"""
                    )
                errors.append(error_message)
                continue
            except (ValueError, TypeError) as e:
                errors.append(
                    f"工具调用解析出错：第{i+1}个code block解析时发生错误: {str(e)}\n"
                    f"内容: {repr_obj.repr(block['content'])}"
                )

    return tool_calls, errors
