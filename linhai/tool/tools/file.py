from linhai.tool.base import register_tool, ToolArgInfo
from pathlib import Path
import os


@register_tool(
    name="read_file",
    desc="读取文件",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type=str),
    },
    required_args=["filepath"],
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
文件路径为: {file_path.as_posix()!r}
文件内容如下，不要复读文件内容:
{content}"""


@register_tool(
    name="write_file",
    desc="写入文件内容，如果没有必要则不要使用这个tool，而是优先使用replace_file_content或者append_file修改文件",
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
    return f"成功写入文件: {file_path.as_posix()!r}"


@register_tool(
    name="append_file",
    desc="追加文件内容",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type=str),
        "content": ToolArgInfo(desc="要在文件后追加的内容", type=str),
    },
    required_args=["filepath", "content"],
)
def append_file(filepath: str, content: str) -> str:
    file_path = Path(filepath)
    try:
        with file_path.open("a+") as f:
            f.write(content)
    except Exception as exc:
        return f"写入文件时发生错误: {exc!r}"
    return f"成功写入文件: {file_path.as_posix()!r}"


@register_tool(
    name="replace_file_content",
    desc="替换文件内容中的指定字符串。"
    "重要：为确保修改准确性，必须提供包含完整上下文（至少前后5行）的唯一标识字符串。"
    "避免对同一文件多次调用此工具修改相同位置，这可能导致意外结果。",
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
    return f"文件内容已替换，路径: {file_path.as_posix()!r}"


@register_tool(
    name="list_files",
    desc="列出指定文件夹中的文件(使用./表示当前文件夹)",
    args={
        "dirpath": ToolArgInfo(desc="文件夹路径，使用./表示当前目录", type=str),
    },
    required_args=["dirpath"],
)
def list_files(dirpath: str) -> str:
    if dirpath == "./":
        dirpath = "."
    dir_path = Path(dirpath)
    if not dir_path.exists():
        return f"文件夹路径{dir_path.as_posix()!r}不存在"
    if not dir_path.is_dir():
        return f"路径{dir_path.as_posix()!r}不是文件夹"
    try:
        files = [f.name for f in dir_path.iterdir() if f.is_file()]
        dirs = [d.name for d in dir_path.iterdir() if d.is_dir()]
        return f"""\
文件夹路径: {dir_path.as_posix()}
文件列表:
{"\n".join(files)}
子目录列表:
{"\n".join(dirs)}"""
    except Exception as exc:
        return f"列出文件时发生错误: {exc!r}"


@register_tool(
    name="get_absolute_path",
    desc="获取路径的绝对路径",
    args={
        "path": ToolArgInfo(desc="相对或绝对路径", type=str),
    },
    required_args=["path"],
)
def get_absolute_path(path: str) -> str:
    try:
        abs_path = Path(path).absolute()
        return f"绝对路径: {abs_path.as_posix()}"
    except Exception as exc:
        return f"获取绝对路径时发生错误: {exc!r}"
