from __future__ import annotations

import base64
import shlex
from typing import TYPE_CHECKING, Optional

from linhai.tool.base import (
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
)

if TYPE_CHECKING:
    from .bash_host import BashHostControl

MAX_FILE_SIZE = 131072


def _quote(path: str) -> str:
    return shlex.quote(path)


async def _check_file_readable(host: BashHostControl, filepath: str) -> str:
    rc, _, _ = await host.execute_raw(f"test -e {_quote(filepath)}")
    if rc != 0:
        return f"文件路径{filepath!r}不存在"
    rc, _, _ = await host.execute_raw(f"test -f {_quote(filepath)}")
    if rc != 0:
        return f"路径{filepath!r}不是文件"
    rc, _, _ = await host.execute_raw(f"test -r {_quote(filepath)}")
    if rc != 0:
        return f"文件{filepath!r}不可读"
    return ""


async def _check_file_size(host: BashHostControl, filepath: str) -> str:
    rc, stdout, _ = await host.execute_raw(f"wc -c < {_quote(filepath)}")
    if rc != 0:
        return f"无法获取文件大小: {filepath!r}"
    size_str = stdout.strip()
    if not size_str.isdigit():
        return f"无法解析文件大小: {size_str!r}"
    if int(size_str) > MAX_FILE_SIZE:
        return f"文件{filepath!r}过大（{int(size_str)}字节），超过128k限制，请使用download_file下载到本地"
    return ""


async def read_file(
    host: BashHostControl, filepath: str, show_line_numbers: bool = False
) -> FileContentToolResult | FailedToolResult:
    error = await _check_file_readable(host, filepath)
    if error:
        return FailedToolResult(content=error)
    error = await _check_file_size(host, filepath)
    if error:
        return FailedToolResult(content=error)

    rc, stdout, stderr = await host.execute_raw(
        f"base64 {_quote(filepath)}", timeout=60.0
    )
    if rc != 0:
        return FailedToolResult(content=f"读取文件失败: {stderr}")

    decoded = base64.b64decode(stdout.strip()) if stdout.strip() else b""
    content = decoded.decode("utf-8", errors="replace")
    return FileContentToolResult(
        filepath=filepath, content=content, show_line_numbers=show_line_numbers
    )


async def write_file(
    host: BashHostControl, filepath: str, content: str, override: bool = False
) -> SuccessfulToolResult | FailedToolResult:
    rc, _, _ = await host.execute_raw(
        f"test -d $(dirname {_quote(filepath)}) && test -w $(dirname {_quote(filepath)})"
    )
    if rc != 0:
        return FailedToolResult(content=f"目录不可写: {filepath!r}")

    if override:
        return FailedToolResult(
            content="禁止override: 非master_host，请妥善处理其他机器上的文件，"
            "考虑手动备份到临时目录，如果你确实需要删除重写，尝试rm"
        )

    rc, _, _ = await host.execute_raw(f"test -e {_quote(filepath)}")
    if rc == 0:
        return FailedToolResult(
            content=f"文件{filepath!r}已存在，如果需要覆盖请使用override参数"
        )

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    cmd = f"echo '{encoded}' | base64 -d > {_quote(filepath)}"
    rc, _, stderr = await host.execute_raw(cmd, timeout=30.0)
    if rc != 0:
        return FailedToolResult(content=f"写入文件失败: {stderr}")
    return SuccessfulToolResult(content=f"成功写入文件: {filepath!r}")


async def replace_file_content(
    host: BashHostControl,
    filepath: str,
    old: str,
    new: str,
    replace_times: Optional[int] = None,
) -> SuccessfulToolResult | FailedToolResult:
    error = await _check_file_readable(host, filepath)
    if error:
        return FailedToolResult(content=error)
    error = await _check_file_size(host, filepath)
    if error:
        return FailedToolResult(content=error)

    rc, cksum_out, _ = await host.execute_raw(f"cksum {_quote(filepath)}")
    if rc != 0:
        return FailedToolResult(content=f"无法获取文件校验和: {filepath!r}")
    original_cksum = cksum_out.strip().split()[0] if cksum_out.strip() else ""

    rc, stdout, stderr = await host.execute_raw(
        f"base64 {_quote(filepath)}", timeout=60.0
    )
    if rc != 0:
        return FailedToolResult(content=f"读取文件失败: {stderr}")

    decoded = base64.b64decode(stdout.strip()) if stdout.strip() else b""
    content = decoded.decode("utf-8", errors="replace")

    if old not in content:
        return FailedToolResult(content=f"内容{old!r}在文件{filepath!r}中未找到")

    count = content.count(old)

    if replace_times is None:
        if count != 1:
            return FailedToolResult(
                content=f"内容{old!r}在文件{filepath!r}中找到{count}次匹配。"
                "默认只替换一次匹配，但找到多次匹配。"
                "建议1. 需要替换多处：直接指定替换次数/指定全部替换。"
                "建议2. 明确只替换一处：在old内容中带上更多内容，以精确匹配一处。"
            )
        replace_count = 1
    elif replace_times > 0:
        if count < replace_times:
            return FailedToolResult(
                content=f"内容{old!r}在文件{filepath!r}中只找到{count}次匹配，"
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

    encoded = base64.b64encode(new_content.encode("utf-8")).decode("ascii")
    tmp_path = host.make_temp_path("replace_tmp")
    write_cmd = f"echo '{encoded}' | base64 -d > {_quote(tmp_path)}"
    rc, _, stderr = await host.execute_raw(write_cmd, timeout=30.0)
    if rc != 0:
        return FailedToolResult(content=f"写入临时文件失败: {stderr}")

    verify_cmd = (
        f"_NEW=$(cksum < {_quote(tmp_path)} | awk '{{print $1}}'); "
        f"_OLD=$(cksum < {_quote(filepath)} | awk '{{print $1}}'); "
        f'if [ "$_OLD" != "{original_cksum}" ]; then '
        f"echo 'CHANGED'; "
        f'elif [ "$_NEW" != "$_OLD" ]; then '
        f"mv {_quote(tmp_path)} {_quote(filepath)} && echo 'OK'; "
        f"else echo 'OK'; fi"
    )
    rc, verify_out, stderr = await host.execute_raw(verify_cmd, timeout=30.0)
    if rc != 0:
        return FailedToolResult(content=f"替换文件失败: {stderr}")
    if "CHANGED" in verify_out:
        await host.execute_raw(f"rm -f {_quote(tmp_path)}")
        return FailedToolResult(
            content=f"文件{filepath!r}在修改期间被外部修改，放弃替换"
        )

    await host.execute_raw(f"rm -f {_quote(tmp_path)}")
    return SuccessfulToolResult(
        content=f"路径{filepath!r}的文件内容{old!r}已替换为{new!r}，替换次数: {actual_replace_count}"
    )


async def list_files(
    host: BashHostControl, dirpath: str
) -> SuccessfulToolResult | FailedToolResult:
    rc, _, _ = await host.execute_raw(f"test -d {_quote(dirpath)}")
    if rc != 0:
        return FailedToolResult(content=f"文件夹路径{dirpath!r}不存在或不是文件夹")

    rc, stdout, stderr = await host.execute_raw(
        f"ls -lah {_quote(dirpath)}", timeout=10.0
    )
    if rc != 0:
        return FailedToolResult(content=f"列出文件失败: {stderr}")
    return SuccessfulToolResult(content=stdout)


async def get_absolute_path(
    host: BashHostControl, path: str
) -> SuccessfulToolResult | FailedToolResult:
    rc, stdout, stderr = await host.execute_raw(
        f"readlink -f {_quote(path)} 2>/dev/null || realpath {_quote(path)}"
    )
    if rc != 0:
        return FailedToolResult(content=f"获取绝对路径失败: {stderr}")
    abs_path = stdout.strip()
    return SuccessfulToolResult(content=f"绝对路径: {abs_path}")


async def read_file_with_sed(
    host: BashHostControl, expression: str, filepath: str
) -> SuccessfulToolResult | FailedToolResult:
    error = await _check_file_readable(host, filepath)
    if error:
        return FailedToolResult(content=error)

    rc, stdout, stderr = await host.execute_raw(
        f"sed -n {shlex.quote(expression)} {_quote(filepath)}", timeout=30.0
    )
    if rc != 0:
        return FailedToolResult(content=f"sed执行失败: {stderr}")
    if expression.startswith("s"):
        return FailedToolResult(content="错误: 表达式以s开头，但此工具不能修改文件!")
    if len(stdout) > MAX_FILE_SIZE:
        return FailedToolResult(
            content=f"错误: sed输出过大（{len(stdout)}字符），超过128k限制。请使用更精确的sed表达式以减少输出。"
        )
    return SuccessfulToolResult(content=stdout)
