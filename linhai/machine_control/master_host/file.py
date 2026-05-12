"""文件操作工具模块，提供文件读写、内容替换等功能。"""

from pathlib import Path
from typing import Callable
import difflib
import itertools
import stat
import subprocess
import time

import pathspec

from linhai.tool.base import (
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
)
from linhai.utils.tokenizer import count_tokens

TOKEN_THRESHOLD = 300


def find_most_similar_in_files(search_string: str, content: str, top_n: int = 3):
    """在内容中查找与搜索字符串最相似的部分。

    Args:
        search_string: 要搜索的字符串
        content: 要搜索的内容
        top_n: 返回前N个最相似的结果

    Returns:
        使用<<alternative>>包裹的相似内容字符串
        当块内容超过300 token时，仅返回位置信息而不返回完整内容
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
    results = []
    for similarity, chunk_index, chunk_content in similarities[:top_n]:
        start_line = chunk_index + 1
        end_line = chunk_index + linenum
        token_count = count_tokens(chunk_content)
        if token_count > TOKEN_THRESHOLD:
            message = f"相似度: {similarity:.2%}, 行号: {start_line}-{end_line}, 内容超过{TOKEN_THRESHOLD} token已省略"
            results.append(
                f"<<alternative>><<message>>{message}<<message>><<alternative>>"
            )
        else:
            message = f"相似度: {similarity:.2%}, 行号: {start_line}-{end_line}"
            results.append(
                f"<<alternative>><<message>>{message}<<message>><<chunk>>{chunk_content}<<chunk>><<alternative>>"
            )
    return "\n".join(results)


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

    file_size = file_path.stat().st_size
    if isinstance(file_size, int) and file_size > 1024 * 1024:
        return f"文件{file_path.as_posix()!r}过大（{file_size}字节），超过1MB限制"

    try:
        _ = file_path.read_text(encoding="utf-8")

    except UnicodeDecodeError:
        return f"文件{file_path.as_posix()!r}不是纯文本文件（UTF-8编码错误）"
    except OSError as exc:
        return f"读取文件时发生错误: {exc!r}"

    return ""


def validate_file_for_sed(file_path: Path) -> str:
    """专门为read_file_with_sed验证文件：检查是否存在、是文件、是纯文本，但不检查文件大小。

    Args:
        file_path: 文件路径对象

    Returns:
        空字符串如果验证通过，否则错误消息
    """
    if not file_path.exists():
        return f"文件路径{file_path.as_posix()!r}不存在"
    if not file_path.is_file():
        return f"路径{file_path.as_posix()!r}不是文件"

    try:
        _ = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"文件{file_path.as_posix()!r}不是纯文本文件（UTF-8编码错误）"
    except OSError as exc:
        return f"读取文件时发生错误: {exc!r}"

    return ""


def read_file(
    filepath: str, show_line_numbers: bool = False
) -> FileContentToolResult | FailedToolResult:
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
        return FailedToolResult(content=validation_error)

    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return FailedToolResult(content=f"发生错误: {exc!r}")

    return FileContentToolResult(
        filepath=file_path.as_posix(),
        content=content,
        show_line_numbers=show_line_numbers,
    )


def write_file(
    filepath: str, content: str, override: bool = False
) -> SuccessfulToolResult | FailedToolResult:
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
            return FailedToolResult(
                content=f"文件{filepath!r}已存在，如果需要覆盖请使用override参数"
            )
        validation_error = validate_file(file_path)
        if validation_error:
            return FailedToolResult(content=validation_error)
    try:
        file_path.write_text(content, encoding="utf-8")
        if not file_path.exists():
            return FailedToolResult(
                content=f"文件写入后验证失败: {file_path.as_posix()!r} 不存在"
            )
        actual = file_path.read_text(encoding="utf-8")
        if actual != content:
            return FailedToolResult(
                content=f"文件写入后验证失败: {file_path.as_posix()!r} 内容不匹配"
            )
    except OSError as exc:
        return FailedToolResult(content=f"写入文件时发生错误: {exc!r}")
    return SuccessfulToolResult(content=f"成功写入文件: {file_path.as_posix()!r}")


def replace_file_content(
    filepath: str, old: str, new: str, replace_times: int | None = None
) -> SuccessfulToolResult | FailedToolResult:
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
        return FailedToolResult(content=validation_error)
    try:
        content = file_path.read_text(encoding="utf-8")
        if old not in content:
            return FailedToolResult(
                content=f"内容{old!r}在文件{file_path.as_posix()!r}中未找到。"
                f"内容类似的部分如下: {find_most_similar_in_files(old, content)}"
            )

        count = content.count(old)

        if replace_times is None:

            if count != 1:
                return FailedToolResult(
                    content=f"内容{old!r}在文件{file_path.as_posix()!r}中找到{count}次匹配。"
                    "默认只替换一次匹配，但找到多次匹配。"
                    "建议1. 需要替换多处：直接指定替换次数/指定全部替换。"
                    "建议2. 明确只替换一处：在old内容中带上更多内容，以精确匹配一处。"
                )
            replace_count = 1
        elif replace_times > 0:

            if count < replace_times:
                return FailedToolResult(
                    content=f"内容{old!r}在文件{file_path.as_posix()!r}中只找到{count}次匹配，"
                    f"但要求替换{replace_times}次。"
                )
            replace_count = replace_times
        elif replace_times == -1:
            replace_count = -1
        else:
            return FailedToolResult(
                content=f"无效的replace_times参数值: {replace_times}，应为正数或-1"
            )

        if replace_count == -1:
            new_content = content.replace(old, new)
            actual_replace_count = count
        else:
            new_content = content.replace(old, new, replace_count)
            actual_replace_count = replace_count

        file_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        return FailedToolResult(content=f"替换内容时发生错误: {exc!r}")
    return SuccessfulToolResult(
        content=f"路径{file_path.as_posix()!r}的文件内容{old!r}已替换为{new!r}，替换次数: {actual_replace_count}"
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
    return f"{size}B"


def get_file_info(file_path: Path) -> str:
    """获取文件的详细信息，类似ls -lah格式"""
    try:
        stat_info = file_path.stat()

        mode = stat_info.st_mode
        file_type = "d" if file_path.is_dir() else "-"
        permissions = format_permissions(mode)

        size_str = format_file_size(stat_info.st_size)

        mtime = time.strftime("%b %d %H:%M", time.localtime(stat_info.st_mtime))

        return f"{file_type}{permissions} {stat_info.st_nlink:>2} {stat_info.st_uid:>4} {stat_info.st_gid:>4} {size_str:>8} {mtime} {file_path.name}"
    except OSError:

        file_type = "d" if file_path.is_dir() else "-"
        return (
            f"{file_type}?????????  ?    ?    ?         ? ??? ?? ???? {file_path.name}"
        )


def list_files(dirpath: str) -> SuccessfulToolResult | FailedToolResult:
    """列出指定文件夹中的文件和子目录。

    Args:
        dirpath: 文件夹路径

    Returns:
        包含文件列表和子目录列表的字符串
    """
    dir_path = Path(dirpath)
    if not dir_path.exists():
        return FailedToolResult(content=f"文件夹路径{dir_path.as_posix()!r}不存在")
    if not dir_path.is_dir():
        return FailedToolResult(content=f"路径{dir_path.as_posix()!r}不是文件夹")
    try:

        items = []
        for item in dir_path.iterdir():
            items.append(get_file_info(item))

        items.sort(key=lambda x: x.split()[-1])

        items_str = "\n".join(items)
        return SuccessfulToolResult(content=f"""\
文件夹路径: {dir_path.as_posix()}
总用量 {len(items)}
{items_str}""")
    except OSError as exc:
        return FailedToolResult(content=f"列出文件时发生错误: {exc!r}")


GLOB_FILE_LIMIT = 5000


def _load_gitignore_spec(base: Path) -> pathspec.PathSpec | None:
    gitignore_path = base / ".gitignore"
    if not gitignore_path.is_file():
        return None
    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    return pathspec.PathSpec.from_lines("gitignore", gitignore_text.splitlines())


def list_files_glob(cwd: str, pattern: str) -> SuccessfulToolResult | FailedToolResult:
    if pattern.startswith("/"):
        return FailedToolResult(content="glob模式不支持绝对路径")
    base = Path(cwd)
    if not base.is_dir():
        return FailedToolResult(content=f"当前目录{cwd!r}不存在或不是文件夹")
    spec = _load_gitignore_spec(base)
    files: list[Path] = []
    for file in base.glob(pattern):
        if not file.is_file():
            continue
        if ".git" in file.parts:
            continue
        if spec is not None:
            rel = file.relative_to(base)
            if spec.match_file(str(rel)):
                continue
        files.append(file)
        if len(files) >= GLOB_FILE_LIMIT:
            break
    files.sort(key=lambda f: (len(f.relative_to(base).parts), f.parts))
    truncated = len(files) >= GLOB_FILE_LIMIT
    lines: list[str] = []
    for parent, group in itertools.groupby(files, lambda f: f.parent.as_posix()):
        names = ",".join(f.name for f in group)
        lines.append(f"{parent}/{{{names}}}")
    header = f"glob base: {base.as_posix()}, pattern: {pattern}"
    if truncated:
        header += f" (Showing top {GLOB_FILE_LIMIT} files)"
    total = len(files)
    return SuccessfulToolResult(
        content=f"{header}\n总用量 {total}\n" + "\n".join(lines)
    )


def get_absolute_path(path: str) -> SuccessfulToolResult | FailedToolResult:
    """获取路径的绝对路径。

    Args:
        path: 相对或绝对路径

    Returns:
        绝对路径字符串或错误消息
    """
    try:
        abs_path = Path(path).absolute()
        return SuccessfulToolResult(content=f"绝对路径: {abs_path.as_posix()}")
    except OSError as exc:
        return FailedToolResult(content=f"获取绝对路径时发生错误: {exc!r}")


def _check_small_file(file_path: Path) -> str | None:
    """检查文件是否过小（少于100行且内容少于30000字符）。

    Args:
        file_path: 文件路径对象

    Returns:
        错误消息或None（如果文件足够大）
    """
    try:
        line_count = 0
        char_count = 0
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line_count += 1
                char_count += len(line)
                if line_count >= 100 and char_count >= 30000:
                    return None

        if line_count < 100 and char_count < 30000:
            return (
                f"错误: 文件内容过少（{line_count}行，{char_count}字符），禁止使用read_file_with_sed工具。\n"
                f"建议使用read_file工具直接读取文件内容。"
            )
        return None
    except OSError as exc:
        return f"读取文件内容时发生错误: {exc!r}"


def read_file_with_sed(
    expression: str,
    filepath: str,
    wrap_argv: Callable[[list[str]], list[str]],
) -> SuccessfulToolResult | FailedToolResult:
    """执行sed表达式并返回输出，不修改文件。

    Args:
        expression: sed表达式
        filepath: 文件路径
        wrap_argv: 将argv用沙箱包裹的回调函数

    Returns:
        sed命令输出或错误消息
    """
    file_path = Path(filepath)
    validation_error = validate_file_for_sed(file_path)
    if validation_error:
        return FailedToolResult(content=validation_error)

    small_file_error = _check_small_file(file_path)
    if small_file_error:
        return FailedToolResult(content=small_file_error)

    try:
        result = subprocess.run(
            wrap_argv(["sed", "-n", expression, file_path.as_posix()]),
            capture_output=True,
            text=True,
            check=True,
        )
        if expression.startswith("s"):
            return FailedToolResult(
                content=f"错误: 表达式以s开头，但此工具不能修改文件!\n{result.stdout=}"
            )

        if len(result.stdout) > 1024 * 1024:
            return FailedToolResult(
                content=f"错误: sed输出过大（{len(result.stdout)}字符），超过1MB限制。请使用更精确的sed表达式以减少输出。"
            )

        return SuccessfulToolResult(content=result.stdout)
    except subprocess.CalledProcessError as exc:
        return FailedToolResult(content=f"sed命令执行错误: {exc.stderr}")
    except OSError as exc:
        return FailedToolResult(content=f"运行sed时发生错误: {exc!r}")
