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
from contextlib import AsyncExitStack
from typing import Any
from functools import partial

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import ToolArgInfo, ToolSet, ToolResultSuccess, ToolResultFailed
from ..group_chat import GroupChat


class MCPConnector:
    def __init__(self, group_chat: GroupChat):
        group_chat.register_member("mcp_connector", self)
        self.group_chat = group_chat
        self.sessions: dict[str, tuple[ClientSession, AsyncExitStack, ToolSet]] = {}
        self.connector_toolset = self.init_connector_toolset()

    def get_toolsets(self) -> list[ToolSet]:
        return [toolset for _, _, toolset in self.sessions.values()] + [
            self.connector_toolset
        ]

    async def connect_mcp_server(
        self, name: str, command: str, exit_stack: AsyncExitStack
    ):
        if name in self.sessions:
            raise RuntimeError(f"Duplicate name: {name!r}")

        command_lst = shlex.split(command)

        server_params = StdioServerParameters(
            command=command_lst[0], args=command_lst[1:], env=None
        )

        reader, writer = await exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        session = await exit_stack.enter_async_context(ClientSession(reader, writer))

        await session.initialize()
        await session.send_ping()

        toolset = ToolSet()
        resp = await session.list_tools()
        for mcp_tool in resp.tools:
            func = partial(
                self.call_tool_raw, server_name=name, tool_name=mcp_tool.name
            )
            deco = toolset.register_tool(
                name=f"mcp_{name}_{mcp_tool.name}",
                desc=(
                    mcp_tool.description if mcp_tool.description else "<No description>"
                ),
                args={
                    "args": ToolArgInfo(
                        desc="此MCP工具的参数，一个object，各个参数如以下json schema所示",
                        type=mcp_tool.inputSchema,
                    ),
                },
                required_args=["args"],
            )
            deco(func)

        self.sessions[name] = (session, exit_stack, toolset)
        return self.sessions[name]

    async def disconnect_mcp_server(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists")
        _, exit_stack, _ = self.sessions.pop(name)
        await exit_stack.aclose()

    async def disconnect_all_mcp_servers(self):
        coros = [exit_stack.aclose() for _, exit_stack, _ in self.sessions.values()]
        await asyncio.gather(*coros)
        self.sessions = {}

    def get_server(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists or not connected")
        return self.sessions[name][0]

    async def call_tool_raw(
        self, server_name: str, tool_name: str, args: dict[str, Any]
    ):
        try:
            data = await self.get_server(server_name).call_tool(
                tool_name, arguments=args
            )
            result = f"{data.meta=}\n"
            for content in data.content:
                if content.type == "text":
                    result += content.text
            return result
        except Exception as e:  # pylint: disable=broad-exception-caught
            return ToolResultFailed(content=f"调用时发生错误：{type(e)} {e!r}")

    def init_connector_toolset(self):
        connector_toolset = ToolSet()

        @connector_toolset.register_tool(
            name="connect_mcp_server",
            desc="通过stdio连接到一个外部服务（本地脚本）",
            args={
                "name": ToolArgInfo(
                    desc="MCP服务器的名字，为这个MCP服务器命名", type="str"
                ),
                "command": ToolArgInfo(
                    desc="MCP服务器的连接路径，如python xxx", type="str"
                ),
            },
            required_args=["name", "command"],
            conflict_with=[
                "disconnect_mcp_server",
                "disconnect_all_mcp_servers",
                "list_mcp_servers",
            ],
        )
        async def connect_mcp_server(name: str, command: str):
            exit_stack = AsyncExitStack()
            try:
                _, _, toolset = await self.connect_mcp_server(name, command, exit_stack)
                return ToolResultSuccess(
                    content=f"连接{command!r}成功，名字为{name!r}，添加了以下工具: "
                    + ", ".join(name for name in toolset.tools.keys())
                    + "注意：为了避免工具名称冲突重命名了工具。"
                    + """示例调用: {"name": "xxx", "arguments": {"args": {...}}}"""
                )
            except (
                Exception
            ) as e:  # WHY: MCP SDK写得很差，抛出的错误类型很多且不确定，我们只能直接捕获Exception
                await exit_stack.aclose()
                return ToolResultFailed(content=f"连接{command!r}失败，错误: {e!r}")

        @connector_toolset.register_tool(
            name="disconnect_mcp_server",
            desc="断开一个已连接的外部服务",
            args={
                "name": ToolArgInfo(desc="要断开的MCP服务器名字", type="str"),
            },
            required_args=["name"],
        )
        async def disconnect_mcp_server(name: str):
            try:
                await self.disconnect_mcp_server(name)
                return ToolResultSuccess(content=f"成功断开MCP服务器: {name!r}")
            except RuntimeError as e:
                return ToolResultFailed(content=f"断开失败: {e!r}")

        @connector_toolset.register_tool(
            name="disconnect_all_mcp_servers",
            desc="断开所有已连接的外部服务",
            args={},
            required_args=[],
        )
        async def disconnect_all_mcp_servers():
            try:
                await self.disconnect_all_mcp_servers()
                return ToolResultSuccess(content="成功断开所有MCP服务器")
            except (RuntimeError, ConnectionError, OSError) as e:
                return ToolResultFailed(content=f"断开所有服务器失败: {e!r}")

        @connector_toolset.register_tool(
            name="list_mcp_servers",
            desc="列出所有已连接的外部服务",
            args={},
            required_args=[],
        )
        async def list_mcp_servers():
            if not self.sessions:
                return ToolResultSuccess(content="当前没有已连接的MCP服务器")

            server_names = list(self.sessions.keys())
            return ToolResultSuccess(
                content=f"已连接的MCP服务器 ({len(server_names)}个):\n"
                + "\n".join(f"- {name}" for name in server_names)
            )

        return connector_toolset
