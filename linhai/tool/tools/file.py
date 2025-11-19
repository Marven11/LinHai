"""文件操作工具模块，提供文件读写、内容替换等功能。"""

from pathlib import Path
import difflib
import json
import platform
import stat
import time
from linhai.llm import Message
from linhai.tool.base import (
    global_tools,
    ToolArgInfo,
    ToolResultMessage,
    ToolErrorMessage,
)
import subprocess
import re


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
    return json.dumps(results, indent=2, ensure_ascii=False)


def validate_file(file_path: Path) -> str:
    """验证文件是否适合操作：检查是否存在、是文件、大小不超过1MB，并且是纯文本。

    Args:
        file_path: 文件路径对象

    Returns:
        空字符串如果验证通过，否则错误消息
    """
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"

    # 检查文件大小
    file_size = file_path.stat().st_size
    if isinstance(file_size, int) and file_size > 1024 * 1024:  # 1MB
        return f"文件{file_path.as_posix()!r}过大（{file_size}字节），超过1MB限制"

    # 检查是否为纯文本：尝试读取文件并检查编码
    try:
        _ = file_path.read_text(encoding="utf-8")  # Unused variable content
        # 如果成功读取，则认为是文本文件
    except UnicodeDecodeError:
        return f"文件{file_path.as_posix()!r}不是纯文本文件（UTF-8编码错误）"
    except OSError as exc:
        return f"读取文件时发生错误: {exc!r}"

    return ""  # 验证通过


@global_tools.register_tool(
    name="read_file",
    desc="读取文件",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "show_line_numbers": ToolArgInfo(desc="是否显示行号", type="bool"),
    },
    required_args=["filepath"],
    collapse_with=["write_file", "append_file", "replace_file_content", "modify_file_with_sed", "insert_at_line"],
)
def read_file(
    filepath: str, show_line_numbers: bool = False
) -> ToolResultMessage | ToolErrorMessage:
    """读取文件内容。

    Args:
        filepath: 文件路径
        show_line_numbers: 是否显示行号

    Returns:
        文件内容字符串，包含路径信息
    """
    file_path = Path(filepath)
    validation_error = validate_file(file_path)
    if validation_error:
        return ToolErrorMessage(validation_error)

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ToolErrorMessage(f"发生错误: {exc!r}")

    if show_line_numbers:
        # 添加行号
        lines = content.splitlines()
        numbered_lines = [f"{i+1}: {line}" for i, line in enumerate(lines)]
        formatted_content = "\n".join(numbered_lines)
    else:
        formatted_content = content

    return ToolResultMessage(
        f"""\
文件路径为: {file_path.as_posix()!r}
文件内容如下，不要复读文件内容:
{formatted_content}"""
    )


@global_tools.register_tool(
    name="write_file",
    desc="写入文件内容。"
    "注意：避免输出大量重复内容！修改文件时优先使用replace_file_content或者append_file，复制文件优先使用shell指令",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "content": ToolArgInfo(desc="要写入的内容", type="str"),
        "override": ToolArgInfo(desc="是否覆盖已有文件", type="bool"),
    },
    required_args=["filepath", "content"],
    collapse_with=["read_file", "list_files", "get_absolute_path", "run_sed_expression"],
)
def write_file(
    filepath: str, content: str, override: bool = False
) -> ToolResultMessage | ToolErrorMessage:
    """写入内容到文件。

    Args:
        filepath: 文件路径
        content: 要写入的内容
        override: 是否覆盖已有文件

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    if file_path.exists():
        if not override:
            return ToolErrorMessage(
                f"文件{filepath!r}已存在，如果需要覆盖请使用override参数"
            )
        validation_error = validate_file(file_path)
        if validation_error:
            return ToolErrorMessage(validation_error)
    try:
        file_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return ToolErrorMessage(f"写入文件时发生错误: {exc!r}")
    return ToolResultMessage(f"成功写入文件: {file_path.as_posix()!r}")


@global_tools.register_tool(
    name="append_file",
    desc="追加文件内容。" "建议：在增加文件内容时优先考虑使用此工具或insert工具",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "content": ToolArgInfo(desc="要在文件后追加的内容", type="str"),
        "assume_empty_line": ToolArgInfo(
            desc="是否假设文件以空行结尾，默认为true", type="bool"
        ),
    },
    required_args=["filepath", "content"],
)
def append_file(
    filepath: str, content: str, assume_empty_line: bool = True
) -> ToolResultMessage | ToolErrorMessage:
    """追加内容到文件末尾。

    Args:
        filepath: 文件路径
        content: 要追加的内容
        assume_empty_line: 是否假设文件以空行结尾，默认为true

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    if file_path.exists():
        validation_error = validate_file(file_path)
        if validation_error:
            return ToolErrorMessage(validation_error)

    if not file_path.exists():
        return ToolErrorMessage("文件不存在")
    try:
        old_content = file_path.read_bytes()
        if (
            assume_empty_line
            and not old_content.endswith(b"\n")
            and not content.startswith("\n")
        ):
            return ToolErrorMessage(
                "错误：使用assume_empty_line假设原文件末尾有换行，但是原文件并没有换行，且新内容开头也没有换行。"
                "这会导致原文件的最后一行被修改。"
                "如果你确实需要修改原文件的最后一行，将assume_empty_line设置为false,"
                "如果你不需要修改原文件的最后一行，在content的开头加上换行符\\n"
            )
        with file_path.open("a", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        return ToolErrorMessage(f"写入文件时发生错误: {exc!r}")
    return ToolResultMessage(f"成功写入文件: {file_path.as_posix()!r}")


@global_tools.register_tool(
    name="replace_file_content",
    desc="替换文件内容中的指定字符串。"
    "建议：在修改文件原有内容时优先使用此工具"
    "重要：为确保修改准确性，必须提供包含完整上下文（至少前后5行）的唯一标识字符串。"
    "避免对同一文件多次调用此工具修改相同位置，这可能导致意外结果。",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "old": ToolArgInfo(desc="要替换的字符串", type="str"),
        "new": ToolArgInfo(desc="新的字符串", type="str"),
        "replace_times": ToolArgInfo(
            desc="替换次数，正数代表替换次数，-1代表替换所有，默认不提供时验证旧内容只出现一次",
            type="int",
        ),
    },
    required_args=["filepath", "old", "new"],
)
def replace_file_content(
    filepath: str, old: str, new: str, replace_times: int | None = None
) -> ToolResultMessage | ToolErrorMessage:
    """替换文件内容中的指定字符串。

    Args:
        filepath: 文件路径
        old: 要替换的字符串
        new: 新的字符串
        replace_times: 替换次数，正数代表替换次数，-1代表替换所有，默认不提供时验证旧内容只出现一次

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    validation_error = validate_file(file_path)
    if validation_error:
        return ToolErrorMessage(validation_error)
    try:
        content = file_path.read_text(encoding="utf-8")
        if old not in content:
            return ToolErrorMessage(
                f"内容{old!r}在文件{file_path.as_posix()!r}中未找到。"
                f"内容类似的部分如下: {find_most_similar_in_files(old, content)}"
            )

        # 检查匹配次数
        count = content.count(old)

        # 参数验证逻辑
        if replace_times is None:
            # 没有提供参数时，验证旧内容只出现一次
            if count != 1:
                return ToolErrorMessage(
                    f"内容{old!r}在文件{file_path.as_posix()!r}中找到{count}次匹配。"
                    f"默认只替换一次匹配，但找到多次匹配，请明确指定替换次数。"
                    f"内容类似的部分如下: {find_most_similar_in_files(old, content)}"
                )
            replace_count = 1
        elif replace_times > 0:
            # 提供数字n>0时，验证旧内容出现次数不超过n
            if count < replace_times:
                return ToolErrorMessage(
                    f"内容{old!r}在文件{file_path.as_posix()!r}中只找到{count}次匹配，"
                    f"但要求替换{replace_times}次。"
                    f"内容类似的部分如下: {find_most_similar_in_files(old, content)}"
                )
            replace_count = replace_times
        elif replace_times == -1:
            # 提供-1时，验证旧内容至少出现2次
            if count < 2:
                return ToolErrorMessage(
                    f"内容{old!r}在文件{file_path.as_posix()!r}中只找到{count}次匹配，"
                    f"但要求替换所有匹配（至少需要2次匹配）。"
                    f"内容类似的部分如下: {find_most_similar_in_files(old, content)}"
                )
            replace_count = -1  # 表示替换所有
        else:
            return ToolErrorMessage(
                f"无效的replace_times参数值: {replace_times}，应为正数或-1"
            )

        # 根据replace_count决定替换方式
        if replace_count == -1:
            new_content = content.replace(old, new)
            actual_replace_count = count
        else:
            new_content = content.replace(old, new, replace_count)
            actual_replace_count = replace_count

        file_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        return ToolErrorMessage(f"替换内容时发生错误: {exc!r}")
    return ToolResultMessage(
        f"路径{file_path.as_posix()!r}的文件内容{old!r}已替换为{new!r}，替换次数: {actual_replace_count}"
    )


def format_permissions(mode: int) -> str:
    """格式化文件权限字符串。"""
    permissions = [
        "r" if mode & stat.S_IRUSR else "-",
        "w" if mode & stat.S_IWUSR else "-",
        "x" if mode & stat.S_IXUSR else "-",
        "r" if mode & stat.S_IRGRP else "-",
        "w" if mode & stat.S_IWGRP else "-",
        "x" if mode & stat.S_IXGRP else "-",
        "r" if mode & stat.S_IROTH else "-",
        "w" if mode & stat.S_IWOTH else "-",
        "x" if mode & stat.S_IXOTH else "-",
    ]
    return "".join(permissions)


def format_file_size(size: int) -> str:
    """格式化文件大小为人类可读格式。"""
    size_units = ["B", "K", "M", "G", "T"]
    current_size = size
    for i, unit in enumerate(size_units):
        if current_size < 1024.0 or i == len(size_units) - 1:
            size_str = f"{current_size:.1f}{unit}" if i > 0 else f"{current_size}B"
            return size_str
        current_size /= 1024.0
    return f"{size}B"  # 备用


def get_file_info(file_path: Path) -> str:
    """获取文件的详细信息，类似ls -lah格式"""
    try:
        stat_info = file_path.stat()

        # 文件类型和权限
        mode = stat_info.st_mode
        file_type = "d" if file_path.is_dir() else "-"
        permissions = format_permissions(mode)

        # 文件大小（人类可读格式）
        size_str = format_file_size(stat_info.st_size)

        # 修改时间
        mtime = time.strftime("%b %d %H:%M", time.localtime(stat_info.st_mtime))

        return f"{file_type}{permissions} {stat_info.st_nlink:>2} {stat_info.st_uid:>4} {stat_info.st_gid:>4} {size_str:>8} {mtime} {file_path.name}"
    except OSError:
        # 如果无法获取详细信息，返回基本名称
        file_type = "d" if file_path.is_dir() else "-"
        return (
            f"{file_type}?????????  ?    ?    ?         ? ??? ?? ???? {file_path.name}"
        )


@global_tools.register_tool(
    name="list_files",
    desc="列出指定文件夹中的文件(使用./表示当前文件夹)",
    args={
        "dirpath": ToolArgInfo(desc="文件夹路径，使用./表示当前目录", type="str"),
    },
    required_args=["dirpath"],
)
def list_files(dirpath: str) -> ToolResultMessage | ToolErrorMessage:
    """列出指定文件夹中的文件和子目录。

    Args:
        dirpath: 文件夹路径

    Returns:
        包含文件列表和子目录列表的字符串
    """
    dir_path = Path(dirpath)
    if not dir_path.exists():
        return ToolErrorMessage(f"文件夹路径{dir_path.as_posix()!r}不存在")
    if not dir_path.is_dir():
        return ToolErrorMessage(f"路径{dir_path.as_posix()!r}不是文件夹")
    try:
        # 获取所有文件和文件夹的详细信息
        items = []
        for item in dir_path.iterdir():
            items.append(get_file_info(item))

        # 按名称排序
        items.sort()

        items_str = "\n".join(items)
        return ToolResultMessage(
            f"""\
文件夹路径: {dir_path.as_posix()}
总用量 {len(items)}
{items_str}"""
        )
    except OSError as exc:
        return ToolErrorMessage(f"列出文件时发生错误: {exc!r}")


@global_tools.register_tool(
    name="get_absolute_path",
    desc="获取路径的绝对路径",
    args={
        "path": ToolArgInfo(desc="相对或绝对路径", type="str"),
    },
    required_args=["path"],
)
def get_absolute_path(path: str) -> ToolResultMessage | ToolErrorMessage:
    """获取路径的绝对路径。

    Args:
        path: 相对或绝对路径

    Returns:
        绝对路径字符串或错误消息
    """
    try:
        abs_path = Path(path).absolute()
        return ToolResultMessage(f"绝对路径: {abs_path.as_posix()}")
    except OSError as exc:
        return ToolErrorMessage(f"获取绝对路径时发生错误: {exc!r}")


@global_tools.register_tool(
    name="run_sed_expression",
    desc="执行sed表达式并返回输出，不修改文件",
    args={
        "expression": ToolArgInfo(desc="sed表达式，如: 1,1000p", type="str"),
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
    },
    required_args=["expression", "filepath"],
)
def run_sed_expression(expression: str, filepath: str) -> Message:
    """执行sed表达式并返回输出。

    Args:
        expression: sed表达式
        filepath: 文件路径

    Returns:
        sed命令输出或错误消息
    """
    file_path = Path(filepath)
    validation_error = validate_file(file_path)
    if validation_error:
        return ToolErrorMessage(validation_error)
    try:
        result = subprocess.run(
            ["sed", "-n", expression, file_path.as_posix()],
            capture_output=True,
            text=True,
            check=True,
        )
        if expression.startswith("s"):
            return ToolErrorMessage(
                f"错误: 表达式以s开头，但此工具不能修改文件!\n{result.stdout=}"
            )
        return ToolResultMessage(result.stdout)
    except subprocess.CalledProcessError as exc:
        return ToolErrorMessage(f"sed命令执行错误: {exc.stderr}")
    except OSError as exc:
        return ToolErrorMessage(f"运行sed时发生错误: {exc!r}")


@global_tools.register_tool(
    name="modify_file_with_sed",
    desc="使用sed表达式修改文件，支持mac和linux的区别",
    args={
        "expression": ToolArgInfo(desc="sed表达式", type="str"),
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
    },
    required_args=["expression", "filepath"],
)
def modify_file_with_sed(
    expression: str, filepath: str
) -> ToolResultMessage | ToolErrorMessage:
    """使用sed表达式修改文件。

    Args:
        expression: sed表达式
        filepath: 文件路径

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    validation_error = validate_file(file_path)
    if validation_error:
        return ToolErrorMessage(validation_error)
    try:
        # 检测操作系统处理-i选项差异
        system = platform.system()
        if system == "Darwin":  # macOS
            cmd = ["sed", "-i", "", expression, file_path.as_posix()]
        else:  # Linux或其他
            cmd = ["sed", "-i", expression, file_path.as_posix()]
        _ = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )  # Unused variable result

        # 检查表达式是否使用行号匹配

        line_number_pattern = r"^\d+"
        result_text = f"文件{file_path.as_posix()!r}已使用sed表达式修改"
        if re.match(line_number_pattern, expression.strip()):
            result_text += (
                "警告：使用行号匹配并修改文件，文件的行号已经变化！"
                "使用行号匹配是不推荐的行为，之后需要按照内容匹配以避免删除错误！"
            )
        return ToolResultMessage(result_text)
    except subprocess.CalledProcessError as exc:
        return ToolErrorMessage(f"sed命令执行错误: {exc.stderr}")
    except OSError as exc:
        return ToolErrorMessage(f"运行sed时发生错误: {exc!r}")


@global_tools.register_tool(
    name="insert_at_line",
    desc="将内容插入到文件的指定行号位置。内容将会插入到原有行之前，如行号为1则插入到开头，行号为2则插入到第二行之前，第一行之后。"
    "建议：在插入新内容时优先使用此工具，但是在多次修改文件时行号容易变化，此时不要使用此工具以避免出错。"
    "注意：调用时需提供预期插入位置的当前行内容（不含换行符）以验证行号准确性。",
    args={
        "filepath": ToolArgInfo(desc="文件路径", type="str"),
        "line_number": ToolArgInfo(desc="要插入的行号（从1开始）", type="int"),
        "content": ToolArgInfo(desc="要插入的内容", type="str"),
        "expected_line_content": ToolArgInfo(
            desc="预期插入位置的当前行内容（不含换行符）", type="str"
        ),
    },
    required_args=["filepath", "line_number", "content", "expected_line_content"],
)
def insert_at_line(
    filepath: str, line_number: int, content: str, expected_line_content: str
) -> ToolResultMessage | ToolErrorMessage:
    """将内容插入到文件的指定行号位置。

    Args:
        filepath: 文件路径
        line_number: 要插入的行号（从1开始）
        content: 要插入的内容

    Returns:
        成功或错误消息
    """
    file_path = Path(filepath)
    validation_error = validate_file(file_path)
    if validation_error:
        return ToolErrorMessage(validation_error)
    try:
        current_content = file_path.read_text(encoding="utf-8")
        lines = current_content.splitlines(keepends=True)  # 保留换行符
        num_lines = len(lines)

        if line_number < 1 or line_number > num_lines + 1:
            return ToolErrorMessage(
                f"行号{line_number}无效，有效范围是1到{num_lines + 1}"
            )

        # 验证当前行内容是否匹配预期
        if line_number <= num_lines:
            current_line = lines[line_number - 1].rstrip("\n")
            if current_line != expected_line_content:
                return ToolErrorMessage(
                    f"预期行内容不匹配：实际内容为'{current_line}'，预期为'{expected_line_content}'"
                    "你可能需要重新读取文件"
                )
        elif line_number == num_lines + 1:
            # 对于文件末尾的情况，预期内容应为空（因为插入到末尾之后）
            if expected_line_content != "":
                return ToolErrorMessage(
                    f"预期行内容不匹配：文件末尾应无内容，但预期为'{expected_line_content}'"
                    "你可能需要重新读取文件"
                )
        else:
            return ToolErrorMessage(
                f"行号{line_number}超出范围，无法验证" "你可能需要重新读取文件"
            )

        # 如果内容不以换行符结尾，添加一个换行符使其成为完整行
        content_to_insert = content
        if not content.endswith("\n"):
            content_to_insert = content + "\n"

        if line_number == 1:
            new_content = content_to_insert + current_content
        elif line_number == num_lines + 1:
            if current_content.endswith("\n"):
                new_content = current_content + content_to_insert
            else:
                new_content = current_content + "\n" + content_to_insert
        else:
            before = "".join(lines[: line_number - 1])
            after = "".join(lines[line_number - 1 :])
            new_content = before + content_to_insert + after

        file_path.write_text(new_content, encoding="utf-8")
        return ToolResultMessage(
            f"成功在文件{file_path.as_posix()!r}的第{line_number}行插入内容"
        )
    except OSError as exc:
        return ToolErrorMessage(f"插入内容时发生错误: {exc!r}")
