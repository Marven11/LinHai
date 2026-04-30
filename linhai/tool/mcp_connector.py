"""
I simply hate the name `MCP Client` and `MCP Server`

Maybe Anthropic name it like that because it's actually RPC protocol, but...

The `MCP Client` is not an "client", but something sit between the LLM and
the `MCP Server`, **receiving** tool call requests from LLM and send it.
And the `MCP Server` actually does thing that a client would do:
searching the web, controlling browsers, ...
exposing interfaces for LLM to use.

In summerization:
`MCP Server` behaves as the middle layer, doing the client things
and `MCP Client` connects LLM to the middle layer.
"""

import asyncio
import shlex
from typing import Any
from functools import partial

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import ToolArgInfo, ToolSet, SuccessfulToolResult, FailedToolResult
from ..registry import Registry
from ..sandbox import ProcessSandboxProtocol, NoSandbox
from ..task_supervisor import PlainTaskSupervisor
from ..utils.i18n import t


class MCPServerConnection:
    def __init__(self, name: str, command: str, connector: "MCPConnector"):
        self.name = name
        self.command = command
        self.connector = connector
        self.toolset: ToolSet | None = None
        self._ready_event = asyncio.Event()
        self._close_event = asyncio.Event()
        self._session: ClientSession | None = None
        self._task_handle = PlainTaskSupervisor()

    def start(self) -> None:
        self._task_handle.create_supervised_task(f"mcp_{self.name}", self._run)

    async def wait_ready(self, timeout: float = 30.0) -> None:
        await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)

    async def _run(self) -> None:
        command_lst = shlex.split(self.command)
        server_params = StdioServerParameters(
            command=command_lst[0], args=command_lst[1:], env=None
        )
        async with stdio_client(server_params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                self._session = session
                await session.initialize()
                await session.send_ping()
                toolset = ToolSet()
                resp = await session.list_tools()
                for mcp_tool in resp.tools:
                    func = partial(
                        self.connector.call_tool_raw,
                        server_name=self.name,
                        tool_name=mcp_tool.name,
                    )
                    deco = toolset.register_tool(
                        name=f"mcp_{self.name}_{mcp_tool.name}",
                        desc=(
                            mcp_tool.description
                            if mcp_tool.description
                            else "<No description>"
                        ),
                        args={
                            "args": ToolArgInfo(
                                desc=t(
                                    {
                                        "zh_CN": "此MCP工具的参数，一个object，各个参数如以下json schema所示",
                                        "en": "Arguments for this MCP tool, an object with parameters as described in the JSON schema",
                                    }
                                ),
                                type=mcp_tool.inputSchema,
                            ),
                        },
                        required_args=["args"],
                    )
                    deco(func)
                self.toolset = toolset
                self._ready_event.set()
                await self._close_event.wait()

    async def close(self) -> None:
        self._close_event.set()
        await self._task_handle.wait(f"mcp_{self.name}")


class MCPConnector:
    def __init__(self, registry: Registry):
        registry.register_member("mcp_connector", self)
        self.registry = registry
        self.sessions: dict[str, MCPServerConnection] = {}
        self._saved_session_info: dict[str, dict] = {}
        self.connector_toolset = self.init_connector_toolset()

    def get_toolsets(self) -> list[ToolSet]:
        return [
            conn.toolset for conn in self.sessions.values() if conn.toolset is not None
        ] + [self.connector_toolset]

    async def connect_mcp_server(self, name: str, command: str):
        if name in self.sessions:
            raise RuntimeError(f"Duplicate name: {name!r}")

        conn = MCPServerConnection(name, command, self)
        conn.start()
        await conn.wait_ready()
        self.sessions[name] = conn
        return conn

    async def disconnect_mcp_server(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists")
        conn = self.sessions.pop(name)
        await conn.close()

    def get_server(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists or not connected")
        return self.sessions[name]

    async def call_tool_raw(
        self, server_name: str, tool_name: str, args: dict[str, Any]
    ):
        try:
            conn = self.get_server(server_name)
            assert conn._session is not None
            data = await conn._session.call_tool(tool_name, arguments=args)
            result = f"{data.meta=}\n"
            for content in data.content:
                if content.type == "text":
                    result += content.text
            return SuccessfulToolResult(content=result)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return FailedToolResult(content=f"调用时发生错误：{type(e)} {e!r}")

    def init_connector_toolset(self):
        connector_toolset = ToolSet()

        @connector_toolset.register_tool(
            name="connect_mcp_server",
            desc=t(
                {
                    "zh_CN": "通过stdio连接到一个外部服务（本地脚本）",
                    "en": "Connect to an external service via stdio (local script)",
                }
            ),
            args={
                "name": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "MCP服务器的名字，为这个MCP服务器命名",
                            "en": "Name for the MCP server",
                        }
                    ),
                    type="str",
                ),
                "command": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "MCP服务器的连接路径，如python xxx",
                            "en": "Connection command for the MCP server, e.g. python xxx",
                        }
                    ),
                    type="str",
                ),
            },
            required_args=["name", "command"],
            conflict_with=[
                "list_mcp_servers",
            ],
        )
        async def connect_mcp_server(name: str, command: str):
            sandbox = self.registry.get_member_typechecked(
                "process_sandbox", ProcessSandboxProtocol
            )

            command_lst = shlex.split(command)
            wrapped_argv = sandbox.wrap_argv(command_lst)
            wrapped_command = " ".join(shlex.quote(arg) for arg in wrapped_argv)

            try:
                conn = await self.connect_mcp_server(name, wrapped_command)
                assert conn.toolset is not None
                return SuccessfulToolResult(
                    content=f"连接{command!r}成功，名字为{name!r}，添加了以下工具: "
                    + ", ".join(n for n in conn.toolset.tools.keys())
                    + "注意：为了避免工具名称冲突重命名了工具。"
                    + """示例调用: {"name": "xxx", "arguments": {"args": {...}}}"""
                )
            except (
                Exception
            ) as e:  # WHY: MCP SDK写得很差，抛出的错误类型很多且不确定，我们只能直接捕获Exception
                return FailedToolResult(content=f"连接{command!r}失败，错误: {e!r}")

        @connector_toolset.register_tool(
            name="disconnect_mcp_server",
            desc=t(
                {
                    "zh_CN": "断开一个已连接的外部服务",
                    "en": "Disconnect a connected external service",
                }
            ),
            args={
                "name": ToolArgInfo(
                    desc=t(
                        {
                            "zh_CN": "要断开的MCP服务器名字",
                            "en": "Name of the MCP server to disconnect",
                        }
                    ),
                    type="str",
                ),
            },
            required_args=["name"],
        )
        async def disconnect_mcp_server(name: str):
            try:
                await self.disconnect_mcp_server(name)
                return SuccessfulToolResult(content=f"成功断开MCP服务器: {name!r}")
            except RuntimeError as e:
                return FailedToolResult(content=f"断开失败: {e!r}")

        @connector_toolset.register_tool(
            name="list_mcp_servers",
            desc=t(
                {
                    "zh_CN": "列出所有已连接的外部服务",
                    "en": "List all connected external services",
                }
            ),
            args={},
            required_args=[],
        )
        async def list_mcp_servers():
            if not self.sessions:
                return SuccessfulToolResult(content="当前没有已连接的MCP服务器")

            server_names = list(self.sessions.keys())
            return SuccessfulToolResult(
                content=f"已连接的MCP服务器 ({len(server_names)}个):\n"
                + "\n".join(f"- {name}" for name in server_names)
            )

        return connector_toolset

    def serialize(self) -> dict:
        sessions = {}
        for name, conn in self.sessions.items():
            sessions[name] = {"command": conn.command}
        return {"sessions": sessions}

    def restore_from(self, data: dict) -> None:
        self._saved_session_info = data.get("sessions", {})
        self.sessions = {}

    def register_lifecycle(self) -> None:
        from linhai.agent.lifecycle import Lifecycle

        lifecycle = self.registry.get_member_typechecked("lifecycle", Lifecycle)
        lifecycle.after_conversation_restore.register(self._after_conversation_restore)

    async def _after_conversation_restore(self) -> None:
        if not self._saved_session_info:
            return

        from linhai.agent.messages import RuntimeMessage
        from linhai.agent.message import AgentMessage

        lines = ["conversation恢复：以下MCP服务器在保存时已连接，现已断开:"]
        for name, info in self._saved_session_info.items():
            lines.append(f"  - {name}: 启动命令={info.get('command', 'unknown')}")

        agent_message = self.registry.get_member_typechecked(
            "agent_message", AgentMessage
        )
        agent_message.update_notification_message(
            RuntimeMessage("\n".join(lines)),
            source="mcp_disconnected",
            sort_value=0,
        )
        self._saved_session_info = {}
