from __future__ import annotations

import getpass
import json
import platform
from typing import TYPE_CHECKING, Dict, Optional, Union, Any
from linhai.machine_control.process import ProcessIOError
from linhai.tool.base import (
    ToolArgInfo,
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
    ToolSet,
)
from linhai.utils.i18n import t

if TYPE_CHECKING:
    from .http_message import HttpToolResult, HttpTextDiffToolResult
    from .main import MachineControl


def register_machine_control_tools(machine_control: "MachineControl") -> ToolSet:
    """注册所有工具"""
    toolset = ToolSet()

    @toolset.register_tool(
        name="list_terminals",
        desc=t(
            {
                "zh_CN": "列出所有机器上的所有终端",
                "en": "List all terminals on all machines",
            }
        ),
        args={},
        required_args=[],
    )
    async def list_terminals_tool() -> SuccessfulToolResult | FailedToolResult:
        return await machine_control.list_all_terminals()

    @toolset.register_tool(
        name="list_machines",
        desc=t({"zh_CN": "列出所有可用的机器", "en": "List all available machines"}),
        args={},
        required_args=[],
    )
    async def list_machines_tool() -> SuccessfulToolResult:
        return await machine_control.list_machines()

    @toolset.register_tool(
        name="get_meta",
        desc=t(
            {
                "zh_CN": "获得当前机器代号、hostname、用户名、LLM名、上下文红绿灯等编排上下文信息",
                "en": "Get current machine ID, hostname, username, LLM name, context traffic light and other orchestration context info",
            }
        ),
        args={},
        required_args=[],
    )
    async def get_meta_tool() -> SuccessfulToolResult:
        from linhai.agent.main import Agent
        from linhai.agent.orchestration import AgentContextOrchestration
        from linhai.llm_manager import LlmManager

        result: dict[str, Any] = {
            "machine_id": machine_control.target_machine,
            "hostname": platform.node(),
            "username": getpass.getuser(),
        }

        llm_manager = machine_control.registry.get_member_typechecked(
            "llm_manager", LlmManager
        )
        result["llm_name"] = llm_manager.get_current_llm().get_name()

        orchestration = machine_control.registry.get_member_typechecked(
            "agent_context_orchestration", AgentContextOrchestration
        )
        agent = machine_control.registry.get_member_typechecked("agent", Agent)
        threshold_info = agent.get_threshold_info()
        result["orchestration_context"] = orchestration.compute_orchestration_context(
            "", threshold_info
        )

        return SuccessfulToolResult(content=json.dumps(result, ensure_ascii=False))

    @toolset.register_tool(
        name="switch_machine",
        desc=t({"zh_CN": "切换到指定机器", "en": "Switch to a specified machine"}),
        args={
            "machine_id": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "机器ID，如'master_host'",
                        "en": "Machine ID, e.g. 'master_host'",
                    }
                ),
                schema={"type": "string"},
            )
        },
        required_args=["machine_id"],
    )
    async def switch_machine_tool(
        machine_id: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        return await machine_control.switch_machine(machine_id)

    @toolset.register_tool(
        name="disconnect_machine",
        desc=t(
            {
                "zh_CN": "断开指定机器的连接，master_host无法断开",
                "en": "Disconnect a specified machine. master_host cannot be disconnected.",
            }
        ),
        args={
            "machine_id": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "要断开的机器ID",
                        "en": "Machine ID to disconnect",
                    }
                ),
                schema={"type": "string"},
            )
        },
        required_args=["machine_id"],
    )
    async def disconnect_machine_tool(
        machine_id: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        return await machine_control.disconnect_machine(machine_id)

    @toolset.register_tool(
        name="connect_posix_shell_as_machine",
        desc=t(
            {
                "zh_CN": "连接已经打开的任何posix shell进程，部署jsonrpc远控进程并操控，支持任何非pty且stdio连接着posix shell(如bash)的进程，可用于sudo bash, docker exec -it sh, adb shell, ssh, nc -l等任何场景打开的posix shell",
                "en": "Connect to any non-pty posix shell process with stdio connected (e.g. bash), deploy jsonrpc control. Supports sudo bash, docker exec -it sh, adb shell, ssh, nc -l, etc.",
            }
        ),
        args={
            "machine_id": ToolArgInfo(
                desc=t({"zh_CN": "新机器的ID", "en": "ID for the new machine"}),
                schema={"type": "string"},
            ),
            "pid": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "要连接的posix shell进程PID",
                        "en": "PID of the posix shell process to connect",
                    }
                ),
                schema={"type": "string"},
            ),
            "source_machine": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "进程所在的机器ID，默认当前机器",
                        "en": "Machine ID where process resides, defaults to current machine",
                    }
                ),
                schema={"type": "string"},
            ),
        },
        required_args=["machine_id", "pid"],
    )
    async def connect_posix_shell_as_machine_tool(
        machine_id: str,
        pid: str,
        source_machine: Optional[str] = None,
    ) -> SuccessfulToolResult | FailedToolResult:
        return await machine_control.add_posix_shell_machine(
            machine_id, pid, source_machine
        )

    @toolset.register_tool(
        name="connect_ether_ghost_machine",
        desc=t(
            {
                "zh_CN": "连接到EtherGhost webshell机器并添加到可用机器列表",
                "en": "Connect to EtherGhost webshell machine and add to available machines",
            }
        ),
        args={
            "machine_id": ToolArgInfo(
                desc=t({"zh_CN": "机器ID", "en": "Machine ID"}),
                schema={"type": "string"},
            ),
            "session_type": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "webshell类型，例如'php_oneliner'",
                        "en": "Webshell type, e.g. 'php_oneliner'",
                    }
                ),
                schema={"type": "string"},
            ),
            "connection_args": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "连接参数字典，根据session类型而定",
                        "en": "Connection arguments dict, varies by session type",
                    }
                ),
                schema={"type": "object"},
            ),
        },
        required_args=["machine_id", "session_type", "connection_args"],
    )
    async def connect_ether_ghost_machine_tool(
        machine_id: str,
        session_type: str,
        connection_args: Dict[str, Any],
    ) -> SuccessfulToolResult | FailedToolResult:
        return await machine_control.add_ether_ghost_machine(
            machine_id, session_type, connection_args
        )

    @toolset.register_tool(
        name="ether_ghost_get_connection_args_definition",
        desc=t(
            {
                "zh_CN": "获取EtherGhost各session类型所需的连接参数定义",
                "en": "Get connection args definition for each EtherGhost session type",
            }
        ),
        args={},
        required_args=[],
    )
    async def ether_ghost_get_connection_args_definition_tool() -> (
        SuccessfulToolResult | FailedToolResult
    ):
        from ether_ghost.core.base import session_type_info

        definition = {}
        for session_type, info in session_type_info.items():
            connection_args = info.get("connection_args", [])
            args_def = {}
            for arg in connection_args:
                args_def[arg["name"]] = {
                    "type": arg.get("type", "str"),
                    "description": arg.get("description", ""),
                    "required": arg.get("required", False),
                    "default": arg.get("default", None),
                }
            definition[session_type] = args_def
        result = {"type": "ether_ghost", "connection_args_definition": definition}
        return SuccessfulToolResult(content=json.dumps(result, ensure_ascii=False))

    @toolset.register_tool(
        name="http_request",
        desc=t(
            {
                "zh_CN": "使用httpx库发送HTTP请求并获取响应内容",
                "en": "Send HTTP requests using httpx and get response content",
            }
        ),
        args={
            "method": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "HTTP方法，如GET、POST",
                        "en": "HTTP method, e.g. GET, POST",
                    }
                ),
                schema={"type": "string"},
            ),
            "url": ToolArgInfo(
                desc=t({"zh_CN": "请求的URL", "en": "Request URL"}),
                schema={"type": "string"},
            ),
            "params": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "查询参数（字典形式）",
                        "en": "Query parameters (as dict)",
                    }
                ),
                schema={"type": "object"},
            ),
            "headers": ToolArgInfo(
                desc=t(
                    {"zh_CN": "请求头（字典形式）", "en": "Request headers (as dict)"}
                ),
                schema={"type": "object"},
            ),
            "data": ToolArgInfo(
                desc=t({"zh_CN": "请求体数据", "en": "Request body data"}),
                schema={"type": "string"},
            ),
            "follow_redirects": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "是否跟随重定向，默认False",
                        "en": "Whether to follow redirects, default False",
                    }
                ),
                schema={"type": "boolean"},
            ),
            "timeout": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "超时时间（秒），默认60秒",
                        "en": "Timeout in seconds, default 60",
                    }
                ),
                schema={"type": "integer"},
            ),
            "auth": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "认证参数，如['username', 'password']",
                        "en": "Auth params, e.g. ['username', 'password']",
                    }
                ),
                schema={"type": "array", "items": {"type": "string"}},
            ),
            "cookies": ToolArgInfo(
                desc=t({"zh_CN": "Cookie字典", "en": "Cookie dict"}),
                schema={"type": "object"},
            ),
            "json_data": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "JSON数据（与data互斥）",
                        "en": "JSON data (mutually exclusive with data)",
                    }
                ),
                schema={"type": "object"},
            ),
            "proxy": ToolArgInfo(
                desc=t({"zh_CN": "代理URL", "en": "Proxy URL"}),
                schema={"type": "string"},
            ),
            "verify": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "SSL验证，True/False/ssl.SSLContext",
                        "en": "SSL verification, True/False/ssl.SSLContext",
                    }
                ),
                schema={"type": "boolean"},
            ),
        },
        required_args=["method", "url"],
    )
    async def http_request_tool(
        method: str,
        url: str,
        params: Optional[Dict[str, Union[str, int, float, bool]]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        follow_redirects: bool = False,
        timeout: int = 60,
        auth: Optional[tuple[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        proxy: Optional[str] = None,
        verify: Optional[bool] = None,
    ) -> HttpToolResult | HttpTextDiffToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        if auth is not None:
            auth = (auth[0], auth[1])
        return await host_control.http_request(
            method,
            url,
            params,
            headers,
            data,
            follow_redirects,
            timeout,
            auth,
            cookies,
            json_data,
            proxy,
            verify,
        )

    @toolset.register_tool(
        name="change_directory",
        desc=t(
            {"zh_CN": "改变当前工作目录", "en": "Change the current working directory"}
        ),
        args={
            "directory": ToolArgInfo(
                desc=t({"zh_CN": "目标目录的路径", "en": "Target directory path"}),
                schema={"type": "string"},
            )
        },
        required_args=["directory"],
    )
    async def change_directory_tool(
        directory: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.change_directory(directory)

    @toolset.register_tool(
        name="process_create",
        desc=t(
            {
                "zh_CN": "以非pty模式创建一个进程，等待一段时间后检查状态。如果进程已退出则返回退出码和输出，否则返回运行中状态。进程的stdin/stdout/stderr通过pipe连接，可使用process_stdio_read/write进行交互",
                "en": "Create a process in non-pty mode, wait and check status. Returns exit code and output if exited, otherwise running status. Process stdin/stdout/stderr are connected via pipes, use process_stdio_read/write for interaction",
            }
        ),
        args={
            "argv": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": '进程参数列表，如["ls", "-l", "-a"]',
                        "en": 'Process argument list, e.g. ["ls", "-l", "-a"]',
                    }
                ),
                schema={"type": "array", "items": {"type": "string"}},
            ),
            "wait_second": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "创建进程后等待的秒数，最多等待时间，为None时使用平台默认值(1秒)",
                        "en": "Seconds to wait after creation, None for platform default (1 second)",
                    }
                ),
                schema={"type": "number"},
            ),
            "override_env": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "环境变量字典，默认None表示继承当前环境变量。如果指定则仅覆盖指定的key，其余环境变量保持不变",
                        "en": "Environment variables dict, default None to inherit current environment. If specified, only overrides the given keys, keeping other environment variables unchanged",
                    }
                ),
                schema={"type": "object"},
            ),
            "with_stdin": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "创建进程后立即写入stdin的内容，默认None",
                        "en": "Content to write to stdin immediately after creation, default None",
                    }
                ),
                schema={"type": "string"},
            ),
        },
        required_args=["argv"],
    )
    async def process_create_tool(
        argv: list[str],
        wait_second: Optional[float] = None,
        override_env: Optional[Dict[str, str]] = None,
        with_stdin: Optional[str] = None,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        result = await host_control.create_process(
            argv, wait_second, override_env=override_env
        )
        if not result.success:
            return FailedToolResult(content=result.error or "创建进程失败")
        if result.returncode is not None:
            if with_stdin is not None:
                return FailedToolResult(
                    content=f"写入with_stdin内容失败：程序过早退出\n<<pid>>{result.pid}<<pid>><<returncode>>{result.returncode}<<returncode>><<stdout>>{result.stdout}<<stdout>><<stderr>>{result.stderr}<<stderr>>"
                )
            return SuccessfulToolResult(
                content=f"<<pid>>{result.pid}<<pid>><<returncode>>{result.returncode}<<returncode>><<stdout>>{result.stdout}<<stdout>><<stderr>>{result.stderr}<<stderr>>"
            )
        process = host_control.get_process(result.pid) if result.pid else None
        if process is not None and "lifecycle" in machine_control.registry.members:
            from linhai.agent.lifecycle import Lifecycle
            from linhai.machine_control.process import ProcessCreateInfo

            lifecycle = machine_control.registry.get_member_typechecked(
                "lifecycle", Lifecycle
            )
            await lifecycle.after_process_create.trigger(
                ProcessCreateInfo(
                    process=process,
                    argv=argv,
                    machine_id=machine_control.target_machine,
                )
            )
        if with_stdin is not None:
            if process is None:
                return FailedToolResult(
                    content=f"写入with_stdin内容失败：进程不存在\n<<pid>>{result.pid}<<pid>>"
                )
            write_result = await process.stdio_write(with_stdin, with_enter=True)
            if isinstance(write_result, ProcessIOError):
                return FailedToolResult(
                    content=f"写入with_stdin内容失败：{write_result.error}\n<<pid>>{result.pid}<<pid>>"
                )
            if not write_result.success:
                return FailedToolResult(
                    content=f"写入with_stdin内容失败：{write_result.error}\n<<pid>>{result.pid}<<pid>>"
                )
        return SuccessfulToolResult(
            content=f"<<pid>>{result.pid}<<pid>><<message>>{result.message}<<message>>"
        )

    @toolset.register_tool(
        name="process_stdio_write",
        desc=t(
            {
                "zh_CN": "向进程的标准输入写入内容。",
                "en": "Write content to process stdin.",
            }
        ),
        args={
            "pid": ToolArgInfo(
                desc=t({"zh_CN": "进程ID", "en": "Process ID"}),
                schema={"type": "string"},
            ),
            "content": ToolArgInfo(
                desc=t({"zh_CN": "要写入的内容", "en": "Content to write"}),
                schema={"type": "string"},
            ),
            "with_enter": ToolArgInfo(
                desc=t(
                    {"zh_CN": "是否在末尾添加回车", "en": "Whether to append newline"}
                ),
                schema={"type": "boolean"},
            ),
        },
        required_args=["pid", "content", "with_enter"],
    )
    async def process_stdio_write_tool(
        pid: str, content: str, with_enter: bool
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return FailedToolResult(content=f"进程不存在: {pid}")
        write_result = await proc.stdio_write(content, with_enter)
        if isinstance(write_result, ProcessIOError):
            return FailedToolResult(content=write_result.error)
        if not write_result.success:
            return FailedToolResult(content=write_result.error or "写入失败")
        return SuccessfulToolResult(content=write_result.message)

    @toolset.register_tool(
        name="process_stdio_read",
        desc=t(
            {
                "zh_CN": "读取进程的标准输出和标准错误内容。",
                "en": "Read process stdout and stderr.",
            }
        ),
        args={
            "pid": ToolArgInfo(
                desc=t({"zh_CN": "进程ID", "en": "Process ID"}),
                schema={"type": "string"},
            ),
            "timeout": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "超时时间（秒），默认60秒",
                        "en": "Timeout in seconds, default 60",
                    }
                ),
                schema={"type": "number"},
            ),
        },
        required_args=["pid"],
    )
    async def process_stdio_read_tool(
        pid: str, timeout: float = 60.0
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return FailedToolResult(content=f"进程不存在: {pid}")
        read_result = await proc.stdio_read(timeout)
        if isinstance(read_result, ProcessIOError):
            return FailedToolResult(content=read_result.error)
        if not read_result.success:
            return FailedToolResult(content=read_result.error or "读取失败")
        stdout_text = read_result.stdout.decode("utf-8", errors="replace")
        stderr_text = read_result.stderr.decode("utf-8", errors="replace")
        exit_note = read_result.exit_note or ""
        return SuccessfulToolResult(
            content=f"<<pid>>{pid}<<pid>><<stdout>>{stdout_text}<<stdout>><<stderr>>{stderr_text}<<stderr>>{exit_note}"
        )

    @toolset.register_tool(
        name="process_wait",
        desc=t(
            {
                "zh_CN": "等待进程结束，带超时设置。",
                "en": "Wait for process to exit with timeout.",
            }
        ),
        args={
            "pid": ToolArgInfo(
                desc=t({"zh_CN": "进程ID", "en": "Process ID"}),
                schema={"type": "string"},
            ),
            "timeout": ToolArgInfo(
                desc=t({"zh_CN": "超时时间（秒）", "en": "Timeout in seconds"}),
                schema={"type": "number"},
            ),
        },
        required_args=["pid", "timeout"],
    )
    async def process_wait_tool(
        pid: str, timeout: float
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return FailedToolResult(content=f"进程不存在: {pid}")
        wait_result = await proc.wait(timeout)
        if isinstance(wait_result, ProcessIOError):
            return FailedToolResult(content=wait_result.error)
        if not wait_result.success:
            return FailedToolResult(content=wait_result.error or "等待失败")
        if wait_result.returncode is None:
            return SuccessfulToolResult(
                content=f"<<pid>>{pid}<<pid>><<message>>等待超时，进程仍在运行<<message>>"
            )
        return SuccessfulToolResult(
            content=f"<<pid>>{pid}<<pid>><<returncode>>{wait_result.returncode}<<returncode>><<stdout>>{wait_result.stdout}<<stdout>><<stderr>>{wait_result.stderr}<<stderr>>"
        )

    @toolset.register_tool(
        name="process_kill",
        desc=t(
            {
                "zh_CN": "杀死进程，可选择优雅终止。",
                "en": "Kill a process, optionally with graceful termination.",
            }
        ),
        args={
            "pid": ToolArgInfo(
                desc=t({"zh_CN": "进程ID", "en": "Process ID"}),
                schema={"type": "string"},
            ),
            "graceful": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "是否优雅终止进程，默认为True",
                        "en": "Whether to gracefully terminate, default True",
                    }
                ),
                schema={"type": "boolean"},
            ),
        },
        required_args=["pid"],
    )
    async def process_kill_tool(
        pid: str, graceful: bool = True
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        proc = host_control.get_process(pid)
        if proc is None:
            return FailedToolResult(content=f"进程不存在: {pid}")
        kill_result = await proc.kill(graceful)
        if isinstance(kill_result, ProcessIOError):
            return FailedToolResult(content=kill_result.error)
        if not kill_result.success:
            return FailedToolResult(content=kill_result.error or "终止进程失败")
        return SuccessfulToolResult(content=kill_result.message or f"进程 {pid} 已终止")

    @toolset.register_tool(
        name="terminal_create",
        desc=t(
            {
                "zh_CN": "在当前机器上新建虚拟终端，返回终端对应的ID。终端高度固定且不能滚动，会截断命令输出结果，因此没有必要则优先使用process_create",
                "en": "Create a virtual terminal on the current machine. Terminal height is fixed and non-scrollable, prefer process_create when possible",
            }
        ),
        args={
            "columns": ToolArgInfo(
                desc=t(
                    {"zh_CN": "终端列数，默认80", "en": "Terminal columns, default 80"}
                ),
                schema={"type": "integer"},
            ),
            "lines": ToolArgInfo(
                desc=t(
                    {"zh_CN": "终端行数，默认24", "en": "Terminal lines, default 24"}
                ),
                schema={"type": "integer"},
            ),
        },
        required_args=[],
    )
    async def create_terminal_tool(
        columns: int = 80, lines: int = 24
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_create(columns, lines)

    @toolset.register_tool(
        name="terminal_send_keys",
        desc=t(
            {
                "zh_CN": "发送按键列表到终端，特殊按键的定义和pyautogui相同，普通按键则传入对应字符，如'a'。如果需要发送ctrl+c等控制字符，请传入对应的控制键名称，如'ctrl+c'、'ctrl+d'等。",
                "en": "Send key list to terminal. Special keys follow pyautogui, regular keys use chars like 'a'. For control chars use 'ctrl+c', 'ctrl+d'.",
            }
        ),
        args={
            "terminal_id": ToolArgInfo(
                desc=t({"zh_CN": "终端ID", "en": "Terminal ID"}),
                schema={"type": "string"},
            ),
            "keys": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": '按键名称列表，如["esc", ":", "q", "enter"]',
                        "en": 'Key name list, e.g. ["esc", ":", "q", "enter"]',
                    }
                ),
                schema={"type": "array"},
            ),
        },
        required_args=["terminal_id", "keys"],
    )
    async def send_keys_to_terminal_tool(
        terminal_id: str, keys: list[str]
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_send_keys(terminal_id, keys)

    @toolset.register_tool(
        name="terminal_send_string",
        desc=t(
            {
                "zh_CN": "发送命令等字符串到终端",
                "en": "Send string such as commands to terminal",
            }
        ),
        args={
            "terminal_id": ToolArgInfo(
                desc=t({"zh_CN": "终端ID", "en": "Terminal ID"}),
                schema={"type": "string"},
            ),
            "string": ToolArgInfo(
                desc=t({"zh_CN": "要发送的字符串", "en": "String to send"}),
                schema={"type": "string"},
            ),
            "with_enter": ToolArgInfo(
                desc=t({"zh_CN": "是否发送enter", "en": "Whether to send enter"}),
                schema={"type": "boolean"},
            ),
            "wait_seconds": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "等待一段时间后读取最新画面，默认等待0.3秒",
                        "en": "Wait before reading screen, default 0.3s",
                    }
                ),
                schema={"type": "number"},
            ),
        },
        required_args=["terminal_id", "string", "with_enter"],
    )
    async def send_string_to_terminal_tool(
        terminal_id: str, string: str, with_enter: bool, wait_seconds: float = 0.3
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_send_string(
            terminal_id, string, with_enter, wait_seconds
        )

    @toolset.register_tool(
        name="terminal_read_screen",
        desc=t(
            {
                "zh_CN": "读取当前终端的屏幕内容",
                "en": "Read current terminal screen content",
            }
        ),
        args={
            "terminal_id": ToolArgInfo(
                desc=t({"zh_CN": "终端ID", "en": "Terminal ID"}),
                schema={"type": "string"},
            )
        },
        required_args=["terminal_id"],
    )
    async def read_terminal_screen_tool(
        terminal_id: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_read_screen(terminal_id)

    @toolset.register_tool(
        name="terminal_close",
        desc=t({"zh_CN": "关闭终端", "en": "Close a terminal"}),
        args={
            "terminal_id": ToolArgInfo(
                desc=t({"zh_CN": "终端ID", "en": "Terminal ID"}),
                schema={"type": "string"},
            )
        },
        required_args=["terminal_id"],
    )
    async def close_terminal_tool(
        terminal_id: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.terminal_close(terminal_id)

    @toolset.register_tool(
        name="read_file",
        desc=t(
            {
                "zh_CN": "读取文件。注意 - 优先于grep/sed：在需要读取文件时优先使用此工具带上行号读取整个文件，只有在此工具无法读取所有内容时才考虑使用sed!",
                "en": "Read a file. Prefer over grep/sed: use this tool with line numbers first, only consider sed when it can't read all content!",
            }
        ),
        args={
            "filepath": ToolArgInfo(
                desc=t({"zh_CN": "文件路径", "en": "File path"}),
                schema={"type": "string"},
            ),
            "show_line_numbers": ToolArgInfo(
                desc=t({"zh_CN": "是否显示行号", "en": "Whether to show line numbers"}),
                schema={"type": "boolean"},
            ),
        },
        required_args=["filepath"],
    )
    async def read_file_tool(
        filepath: str, show_line_numbers: bool = False
    ) -> Union[SuccessfulToolResult, FailedToolResult, FileContentToolResult]:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.read_file(filepath, show_line_numbers)

    @toolset.register_tool(
        name="write_file",
        desc=t(
            {
                "zh_CN": "写入文件内容。注意：不要复述已有的文件内容！如果需要复制必须优先使用shell指令cp！如果需要修改文件必须优先使用replace_file_content！如果需要追加文件内容，用replace_file_content匹配文件末尾几行并追加！",
                "en": "Write file content. Do not restate existing content! Use cp for copying, replace_file_content for modifications and appending!",
            }
        ),
        args={
            "filepath": ToolArgInfo(
                desc=t({"zh_CN": "文件路径", "en": "File path"}),
                schema={"type": "string"},
            ),
            "content": ToolArgInfo(
                desc=t({"zh_CN": "要写入的内容", "en": "Content to write"}),
                schema={"type": "string"},
            ),
            "override": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "是否覆盖已有文件",
                        "en": "Whether to override existing file",
                    }
                ),
                schema={"type": "boolean"},
            ),
        },
        required_args=["filepath", "content"],
    )
    async def write_file_tool(
        filepath: str, content: str, override: bool = False
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.write_file(filepath, content, override)

    @toolset.register_tool(
        name="replace_file_content",
        desc=t(
            {
                "zh_CN": "替换文件内容中的指定字符串。建议：在修改文件原有内容时优先使用此工具。追加、添加内容时：优先使用此工具。使用方法为匹配末尾的几行并添加新内容。",
                "en": "Replace specified string in file content. Prefer for modifying existing content. For appending: match last few lines and add new content.",
            }
        ),
        args={
            "filepath": ToolArgInfo(
                desc=t({"zh_CN": "文件路径", "en": "File path"}),
                schema={"type": "string"},
            ),
            "old": ToolArgInfo(
                desc=t({"zh_CN": "要替换的字符串", "en": "String to replace"}),
                schema={"type": "string"},
            ),
            "new": ToolArgInfo(
                desc=t({"zh_CN": "新的字符串", "en": "New string"}),
                schema={"type": "string"},
            ),
            "replace_times": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "替换次数，正数代表替换次数，-1代表替换所有，默认不提供时验证旧内容只出现一次",
                        "en": "Replace count, positive for count, -1 for all, default verifies old appears only once",
                    }
                ),
                schema={"type": "integer"},
            ),
        },
        required_args=["filepath", "old", "new"],
    )
    async def replace_file_content_tool(
        filepath: str, old: str, new: str, replace_times: Optional[int] = None
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.replace_file_content(
            filepath, old, new, replace_times
        )

    @toolset.register_tool(
        name="list_files",
        desc=t(
            {
                "zh_CN": "列出指定文件夹中的文件(使用./表示当前文件夹)",
                "en": "List files in a directory (use ./ for current directory)",
            }
        ),
        args={
            "dirpath": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "文件夹路径，使用./表示当前目录",
                        "en": "Directory path, use ./ for current directory",
                    }
                ),
                schema={"type": "string"},
            ),
        },
        required_args=["dirpath"],
    )
    async def list_files_tool(
        dirpath: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.list_files(dirpath)

    @toolset.register_tool(
        name="list_files_glob",
        desc=t(
            {
                "zh_CN": "基于glob模式匹配文件，支持*和**等通配符，尊重gitignore。仅master_host支持",
                "en": "Match files using glob patterns with * and ** wildcards, respecting gitignore. Only master_host supported",
            }
        ),
        args={
            "pattern": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "glob匹配模式，如**/*.py、src/**/*.txt。不允许使用绝对路径",
                        "en": "Glob pattern, e.g. **/*.py, src/**/*.txt. Absolute paths not allowed",
                    }
                ),
                schema={"type": "string"},
            ),
        },
        required_args=["pattern"],
    )
    async def list_files_glob_tool(
        pattern: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.list_files_glob(pattern)

    @toolset.register_tool(
        name="get_absolute_path",
        desc=t(
            {"zh_CN": "获取路径的绝对路径", "en": "Get the absolute path of a path"}
        ),
        args={
            "path": ToolArgInfo(
                desc=t({"zh_CN": "相对或绝对路径", "en": "Relative or absolute path"}),
                schema={"type": "string"},
            )
        },
        required_args=["path"],
    )
    async def get_absolute_path_tool(
        path: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.get_absolute_path(path)

    @toolset.register_tool(
        name="read_file_with_sed",
        desc=t(
            {
                "zh_CN": "执行sed表达式并返回输出，不修改文件",
                "en": "Execute sed expression and return output without modifying the file",
            }
        ),
        args={
            "expression": ToolArgInfo(
                desc=t(
                    {
                        "zh_CN": "sed表达式，如: 1,1000p",
                        "en": "sed expression, e.g. 1,1000p",
                    }
                ),
                schema={"type": "string"},
            ),
            "filepath": ToolArgInfo(
                desc=t({"zh_CN": "文件路径", "en": "File path"}),
                schema={"type": "string"},
            ),
        },
        required_args=["expression", "filepath"],
    )
    async def read_file_with_sed_tool(
        expression: str, filepath: str
    ) -> SuccessfulToolResult | FailedToolResult:
        host_control = machine_control.machines[machine_control.target_machine]
        return await host_control.read_file_with_sed(expression, filepath)

    @toolset.register_tool(
        name="transfer_file",
        desc=t(
            {
                "zh_CN": "将文件从一台机器传送到另一台机器上",
                "en": "Transfer a file from one machine to another",
            }
        ),
        args={
            "from_filepath": ToolArgInfo(
                desc=t({"zh_CN": "源文件路径", "en": "Source file path"}),
                schema={"type": "string"},
            ),
            "from_machine": ToolArgInfo(
                desc=t({"zh_CN": "源机器ID", "en": "Source machine ID"}),
                schema={"type": "string"},
            ),
            "to_filepath": ToolArgInfo(
                desc=t({"zh_CN": "目标文件路径", "en": "Destination file path"}),
                schema={"type": "string"},
            ),
            "to_machine": ToolArgInfo(
                desc=t({"zh_CN": "目标机器ID", "en": "Destination machine ID"}),
                schema={"type": "string"},
            ),
        },
        required_args=[
            "from_filepath",
            "from_machine",
            "to_filepath",
            "to_machine",
        ],
    )
    async def transfer_file_tool(
        from_filepath: str,
        from_machine: str,
        to_filepath: str,
        to_machine: str,
    ) -> SuccessfulToolResult | FailedToolResult:
        return await machine_control.transfer_file(
            from_filepath, from_machine, to_filepath, to_machine
        )

    return toolset
