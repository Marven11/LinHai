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
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPConnector:
    def __init__(self):
        self.sessions: dict[str, tuple[ClientSession, AsyncExitStack]] = {}

    async def connect_stdio(self, name: str, server_script_path: str):
        if name in self.sessions:
            raise RuntimeError(f"Duplecate name: {name!r}")
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

        self.sessions[name] = (session, exit_stack)

    async def disconnect(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists")
        _, exit_stack = self.sessions.pop(name)
        await exit_stack.aclose()

    async def disconnect_all(self):
        coros = [exit_stack.aclose() for _, exit_stack in self.sessions.values()]
        await asyncio.gather(*coros)
        self.sessions = {}

    def get_server(self, name: str):
        if name not in self.sessions:
            raise RuntimeError(f"{name!r} not exists or not connected")
        return self.sessions[name][0]
