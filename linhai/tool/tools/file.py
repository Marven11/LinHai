"""文件操作工具模块，提供文件读写、内容替换等功能。"""

from pathlib import Path
import difflib
import json
from linhai.tool.base import register_tool, ToolArgInfo
import subprocess


def find_most_similar_in_files(search_string: str, content: str, top_n: int = 3):
    """在内容中查找与搜索字符串最相似的部分。

    Args:
        search_string: 要搜索的字符串
        content: 要搜索的内容
        top_n: 返回前N个最相似的结果

    Returns:
        包含相似度、行号和内容的字典列表
    """

    linenum = search_string.count("\n") + 1
    lines = content.splitlines()

    chunks = [
        "\n".join(lines[i : i + linenum]) for i in range(0, len(lines) - linenum + 1)
    ]

    similarities = []
    for i, chunk in enumerate(chunks):
        similarity = difflib.SequenceMatcher(None, search_string, chunk).ratio()
        similarities.append((similarity, i, chunk))
    similarities.sort(key=lambda x: x[0], reverse=True)
    results = [
        {
            "similarity": similarity,
            "start_line": chunk_index + 1,
            "end_line": chunk_index + linenum,
            "content": chunk_content,
        }
        for similarity, chunk_index, chunk_content in similarities[:top_n]
    ]

    return results


@register_tool(
    name="read_file",
    desc="读取文件",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "show_line_numbers": ToolArgInfo(desc="是否显示行号", type="bool"),
    },
    required_args=["filepath"],
)
def read_file(filepath: str, show_line_numbers: bool = False) -> str:
    """读取文件内容。

    Args:
        filepath: 文件路径
        show_line_numbers: 是否显示行号

    Returns:
        文件内容字符串，包含路径信息
    """
    file_path = Path(filepath)
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"发生错误: {exc!r}"

    if show_line_numbers:
        # 添加行号
        lines = content.splitlines()
        numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        formatted_content = "\n".join(numbered_lines)
    else:
        formatted_content = content

    return f"""\
文件路径为: {file_path.as_posix()!r}
文件内容如下，不要复读文件内容:
{formatted_content}"""


@register_tool(
    name="write_file",
    desc="写入文件内容，如果没有必要则不要使用这个tool，而是优先使用replace_file_content或者append_file修改文件",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "content": ToolArgInfo(desc="要写入的内容", type="str"),
    },
    required_args=["filepath", "content"],
)
def write_file(filepath: str, content: str) -> str:
    """写入内容到文件。

    Args:
        filepath: 文件路径
        content: 要写入的内容

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    try:
        file_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"写入文件时发生错误: {exc!r}"
    return f"成功写入文件: {file_path.as_posix()!r}"


@register_tool(
    name="append_file",
    desc="追加文件内容",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "content": ToolArgInfo(desc="要在文件后追加的内容", type="str"),
    },
    required_args=["filepath", "content"],
)
def append_file(filepath: str, content: str) -> str:
    """追加内容到文件末尾。

    Args:
        filepath: 文件路径
        content: 要追加的内容

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    try:
        with file_path.open("a+", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return f"写入文件时发生错误: {exc!r}"
    return f"成功写入文件: {file_path.as_posix()!r}"


@register_tool(
    name="replace_file_content",
    desc="替换文件内容中的指定字符串。"
    "重要：为确保修改准确性，必须提供包含完整上下文（至少前后5行）的唯一标识字符串。"
    "避免对同一文件多次调用此工具修改相同位置，这可能导致意外结果。",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "old": ToolArgInfo(desc="要替换的字符串", type="str"),
        "new": ToolArgInfo(desc="新的字符串", type="str"),
    },
    required_args=["filepath", "old", "new"],
)
def replace_file_content(filepath: str, old: str, new: str) -> str:
    """替换文件内容中的指定字符串。

    Args:
        filepath: 文件路径
        old: 要替换的字符串
        new: 新的字符串

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"
    try:
        content = file_path.read_text(encoding="utf-8")
        similar_info = json.dumps(
            find_most_similar_in_files(old, content), indent=2, ensure_ascii=False
        )
        if old not in content:
            return (
                f"内容{old!r}在文件{file_path.as_posix()!r}中未找到。"
                f"内容类似的部分如下: {similar_info}"
            )
        new_content = content.replace(old, new)
        file_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        return f"替换内容时发生错误: {exc!r}"
    return f"路径{file_path.as_posix()!r}的文件内容{old!r}已替换为{new!r}，"


@register_tool(
    name="list_files",
    desc="列出指定文件夹中的文件(使用./表示当前文件夹)",
    args={
        "dirpath": ToolArgInfo(desc="文件夹路径，使用./表示当前目录", type="str"),
    },
    required_args=["dirpath"],
)
def list_files(dirpath: str) -> str:
    """列出指定文件夹中的文件和子目录。

    Args:
        dirpath: 文件夹路径

    Returns:
        包含文件列表和子目录列表的字符串
    """
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
    except OSError as exc:
        return f"列出文件时发生错误: {exc!r}"


@register_tool(
    name="get_absolute_path",
    desc="获取路径的绝对路径",
    args={
        "path": ToolArgInfo(desc="相对或绝对路径", type="str"),
    },
    required_args=["path"],
)
def get_absolute_path(path: str) -> str:
    """获取路径的绝对路径。

    Args:
        path: 相对或绝对路径

    Returns:
        绝对路径字符串或错误消息
    """
    try:
        abs_path = Path(path).absolute()
        return f"绝对路径: {abs_path.as_posix()}"
    except OSError as exc:
        return f"获取绝对路径时发生错误: {exc!r}"


@register_tool(
    name="run_sed_expression",
    desc="执行sed表达式并返回输出，不修改文件",
    args={
        "expression": ToolArgInfo(desc="sed表达式", type="str"),
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
    },
    required_args=["expression", "filepath"],
)
def run_sed_expression(expression: str, filepath: str) -> str:
    """执行sed表达式并返回输出。

    Args:
        expression: sed表达式
        filepath: 文件路径

    Returns:
        sed命令输出或错误消息
    """
    file_path = Path(filepath)
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"
    try:
        # 运行sed命令，不修改文件
        result = subprocess.run(
            ["sed", expression, file_path.as_posix()],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        return f"sed命令执行错误: {exc.stderr}"
    except OSError as exc:
        return f"运行sed时发生错误: {exc!r}"


@register_tool(
    name="modify_file_with_sed",
    desc="使用sed表达式修改文件，支持mac和linux的区别",
    args={
        "expression": ToolArgInfo(desc="sed表达式", type="str"),
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
    },
    required_args=["expression", "filepath"],
)
def modify_file_with_sed(expression: str, filepath: str) -> str:
    """使用sed表达式修改文件。

    Args:
        expression: sed表达式
        filepath: 文件路径

    Returns:
        成功或错误消息
    """
    import platform  # 局部导入以检测操作系统

    file_path = Path(filepath)
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"
    try:
        # 检测操作系统处理-i选项差异
        system = platform.system()
        if system == "Darwin":  # macOS
            cmd = ["sed", "-i", "", expression, file_path.as_posix()]
        else:  # Linux或其他
            cmd = ["sed", "-i", expression, file_path.as_posix()]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"文件{file_path.as_posix()!r}已使用sed表达式修改"
    except subprocess.CalledProcessError as exc:
        return f"sed命令执行错误: {exc.stderr}"
    except OSError as exc:
        return f"运行sed时发生错误: {exc!r}"
