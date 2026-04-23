import os
import sys
from pathlib import Path

import pytest

from linhai.agent.main import Agent
from linhai.agent.conversation import register_conversation_folder
from linhai.config import ToolConfig
from linhai.base import SystemMessage, UserMessage, AssistantMessage
from linhai.llm import OpenAi
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.token_manager import TokenManager
from linhai.tool.base import ToolResultFailed, ToolResultSuccess
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.main import ToolManager
from linhai.task_supervisor import PlainTaskSupervisor

from conftest import retry_llm_call, slim_system_message

pytestmark = pytest.mark.asyncio

DEEPSEEK_BASE_URL = "http://192.168.114.149:8124/v1/deepseek"
DEEPSEEK_MODEL = "deepseek-reasoner"
LLM_NAME = "free"


def _get_server_command() -> str:
    server_path = Path(__file__).resolve().parent / "test_mcp_server.py"
    return f"{sys.executable} {server_path}"


async def _connect_mcp_server(registry: Registry) -> MCPConnector:
    connector = MCPConnector(registry)
    await connector.connect_mcp_server("test", _get_server_command())
    return connector


async def test_mcp_server_connection():
    registry = Registry()
    connector = await _connect_mcp_server(registry)

    conn = connector.get_server("test")
    assert conn.toolset is not None

    tools = conn.toolset.get_tools()
    assert "mcp_test_add" in tools
    assert "mcp_test_multiply" in tools
    assert len(tools) == 2

    await connector.disconnect_mcp_server("test")


async def test_mcp_tool_call():
    registry = Registry()
    connector = await _connect_mcp_server(registry)

    result = await connector.call_tool_raw("test", "add", {"a": 3, "b": 5})
    assert isinstance(result, ToolResultSuccess)
    assert "8" in result.content

    result2 = await connector.call_tool_raw("test", "multiply", {"a": 4, "b": 7})
    assert isinstance(result2, ToolResultSuccess)
    assert "28" in result2.content

    await connector.disconnect_mcp_server("test")


def _get_last_assistant_message(agent: Agent) -> str:
    messages = agent.message_processor.get_messages()
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage):
            return msg.message
    return ""


async def _create_mcp_agent(token: str) -> tuple[Agent, MCPConnector]:
    registry = Registry()
    TokenManager(registry)

    llm = OpenAi(
        registry=registry,
        api_key=token,
        base_url=DEEPSEEK_BASE_URL,
        model=DEEPSEEK_MODEL,
        openai_config={
            "default_headers": {
                "HTTP-Referer": "https://github.com/Marven11/LinHai",
                "X-Title": "LinHai E2E Tests",
            }
        },
        chat_completion_kwargs={"max_tokens": 5000},
        support_image=False,
        explicit_cache_info=None,
        name=LLM_NAME,
    )

    llm_manager = LlmManager(
        registry=registry,
        llms=[llm],
        llm_fallback_map={LLM_NAME: None},
        llm_fallback_duration_map={LLM_NAME: 120},
    )

    mcp_connector = await _connect_mcp_server(registry)

    tool_manager = ToolManager(registry, ToolConfig(), mcp_connector)
    register_conversation_folder(registry)

    system_message = SystemMessage(registry)
    slim_system_message(system_message)
    agent = Agent(
        llm_manager=llm_manager,
        compress_threshold=0.9,
        registry=registry,
        pinned_messages=[system_message],
    )

    tool_manager.register_toolset(
        "llm", agent.toolcall_processor.calculate_llm_toolset()
    )
    tool_manager.register_lifecycle()

    registry.register_queue("parsed_agent_answer")
    registry.register_member("task_supervisor", PlainTaskSupervisor())
    registry.call_postinit()
    return agent, mcp_connector


async def test_mcp_llm_coordination():
    token = "x"

    async def try_once():
        agent, mcp_connector = await _create_mcp_agent(token)

        await agent.message_processor.add_new_message(
            UserMessage(
                "Please use the mcp_test_add tool with a=3 and b=5 to calculate 3+5."
            )
        )
        for _ in range(5):
            await agent.generate_response()

        response = _get_last_assistant_message(agent)
        await mcp_connector.disconnect_mcp_server("test")
        return response if len(response) > 0 and "8" in response else None

    await retry_llm_call(try_once)
