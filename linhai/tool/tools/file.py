from linhai.tool.base import register_tool, ToolArgInfo
from pathlib import Path
import os


@register_tool(
    name="read_file",
    desc="读取文件",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type=float),
    },
    required_args=["a", "b"],
)
def read_file(filepath: str) -> str:
    file_path = Path(filepath)
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"
    try:
        content = file_path.read_text()
    except Exception as exc:
        return f"发生错误: {exc!r}"

    return f"""\
文件路径为: {file_path.as_posix()}
文件内容如下:
{content}"""


@register_tool(
    name="write_file",
    desc="写入文件内容",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type=str),
        "content": ToolArgInfo(desc="要写入的内容", type=str),
    },
    required_args=["filepath", "content"],
)
def write_file(filepath: str, content: str) -> str:
    file_path = Path(filepath)
    try:
        file_path.write_text(content)
    except Exception as exc:
        return f"写入文件时发生错误: {exc!r}"
    return f"成功写入文件: {file_path.as_posix()}"


@register_tool(
    name="replace_file_content",
    desc="替换文件内容中的指定字符串",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type=str),
        "old": ToolArgInfo(desc="要替换的字符串", type=str),
        "new": ToolArgInfo(desc="新的字符串", type=str),
    },
    required_args=["filepath", "old", "new"],
)
def replace_file_content(filepath: str, old: str, new: str) -> str:
    file_path = Path(filepath)
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"
    try:
        content = file_path.read_text()
        if old not in content:
            return f"内容{old!r}在文件{file_path.as_posix()!r}中未找到"
        new_content = content.replace(old, new)
        file_path.write_text(new_content)
    except Exception as exc:
        return f"替换内容时发生错误: {exc!r}"
    return f"文件内容已替换，路径: {file_path.as_posix()}"
