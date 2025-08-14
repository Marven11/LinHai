import json
import mistune
from typing import List, Dict, Any


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
            try:
                data = json.loads(block["content"])
                json_blocks.append(data)
            except json.JSONDecodeError:
                continue
    return json_blocks


def extract_tool_calls(markdown_text: str) -> List[Dict[str, Any]]:
    """
    从Markdown文本中提取JSON格式的工具调用

    Args:
        markdown_text: 要解析的Markdown文本

    Returns:
        包含工具调用信息的列表，每个元素是包含'name'和'arguments'的字典
    """
    json_blocks = extract_json_blocks(markdown_text)
    tool_calls = []
    for data in json_blocks:
        if isinstance(data, dict) and "name" in data and "arguments" in data:
            tool_calls.append(data)
    return tool_calls
