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
# import json  # Unused import
import os.path
from contextlib import AsyncExitStack
from typing import Any
from functools import partial

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .base import ToolArgInfo, ToolSet, ToolErrorMessage, ToolResultMessage
from ..group_chat import GroupChat

class MCPConnector:
    def __init__(self, group_chat: GroupChat):
        group_chat.register_member("mcp_connector", self)
        self.group_chat = group_chat
        self.sessions: dict[str, tuple[ClientSession, AsyncExitStack, ToolSet]] = {}
        self.connector_toolset = self.init_connector_toolset()

    def get_toolsets(self) -> list[ToolSet]:
        return [toolset for _, _, toolset in self.sessions.values()] + [self.connector_toolset]

    async def connect_stdio(self, name: str, server_script_path: str):
        if name in self.sessions:
            raise RuntimeError(f"Duplicate name: {name!r}")
        if not os.path.exists(server_script_path):
            raise RuntimeError(f"Not exists: {server_script_path!r}")

        command = "python" if server_script_path.endswith(".py") else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )
        exit_stack = AsyncExitStack()

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

    async def disconnect(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists")
        _, exit_stack, _ = self.sessions.pop(name)
        await exit_stack.aclose()

    async def disconnect_all(self):
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
        return await self.get_server(server_name).call_tool(tool_name, arguments=args)

    def init_connector_toolset(self):
        connector_toolset = ToolSet()

        @connector_toolset.register_tool(
            name="connect_stdio",
            desc="通过stdio连接到一个MCP服务器（本地脚本）",
            args={
                "name": ToolArgInfo(
                    desc="MCP服务器的名字，为这个MCP服务器命名", type="str"
                ),
                "server_script_path": ToolArgInfo(
                    desc="MCP服务器的文件路径，以.js或.py结尾", type="str"
                ),
            },
            required_args=["name", "server_script_path"],
        )
        async def connect_stdio(name: str, server_script_path: str):
            try:
                _, _, toolset = await self.connect_stdio(name, server_script_path)
                return ToolResultMessage(
                    f"连接{server_script_path!r}成功，名字为{name!r}，添加了以下工具: "
                    + ", ".join(name for name in toolset.tools.keys())
                    + "注意：为了避免工具名称冲突重命名了工具。"
                    + """示例调用: {"name": "xxx", "arguments": {"args": {...}}}"""
                )
            except (ConnectionError, TimeoutError) as e:
                return ToolErrorMessage(f"连接{server_script_path!r}失败，错误: {e!r}")

        return connector_toolset
