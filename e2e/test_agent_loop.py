import os
import pytest
from linhai.agent.main import Agent
from linhai.agent.conversation import register_conversation_folder
from linhai.config import ToolConfig
from linhai.llm import Message, OpenAi, SystemMessage, UserMessage, AssistantMessage
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.token_manager import TokenManager
from linhai.tool.base import ToolArgInfo, ToolSet
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.main import ToolManager

from conftest import retry_llm_call, slim_system_message

pytestmark = pytest.mark.asyncio

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openrouter/free"
LLM_NAME = "free"


def _create_test_agent(token: str) -> Agent:
    registry = Registry()
    TokenManager(registry)

    llm = OpenAi(
        registry=registry,
        api_key=token,
        base_url=OPENROUTER_BASE_URL,
        model=OPENROUTER_MODEL,
        openai_config={
            "default_headers": {
                "HTTP-Referer": "https://github.com/Marven11/LinHai",
                "X-Title": "LinHai E2E Tests",
            }
        },
        chat_completion_kwargs={"max_tokens": 300},
        support_image=False,
        explicit_cache_info=None,
        name=LLM_NAME,
    )

    llm_manager = LlmManager(
        registry=registry,
        llms=[llm],
        llm_fallback_map={LLM_NAME: None},
    )

    mcp_connector = MCPConnector(registry)
    tool_manager = ToolManager(registry, ToolConfig(), mcp_connector)

    register_conversation_folder(registry)

    system_message = SystemMessage(registry)
    slim_system_message(system_message)
    pinned_messages: list[Message] = [system_message]

    agent = Agent(
        llm_manager=llm_manager,
        compress_threshold=0.9,
        registry=registry,
        pinned_messages=pinned_messages,
    )

    toolset = _create_test_toolset()
    tool_manager.register_toolset("test", toolset)
    tool_manager.register_toolset(
        "llm", agent.toolcall_processor.calculate_llm_toolset()
    )
    tool_manager.register_lifecycle()

    registry.register_queue("parsed_agent_answer")
    registry.register_member("task_supervisor", PlainTaskSupervisor())
    registry.call_postinit()
    return agent


def _create_test_toolset() -> ToolSet:
    toolset = ToolSet()

    @toolset.register_tool(
        name="get_weather",
        desc="Get the current weather for a given city",
        args={"city": ToolArgInfo(desc="The city name", type="string")},
        required_args=["city"],
    )
    def get_weather(city: str):
        return f"Sunny, 25\u00b0C in {city}"

    return toolset


async def _get_agent() -> Agent:
    token = os.environ.get("OPENROUTER_TOKEN")
    if not token:
        pytest.fail("OPENROUTER_TOKEN not set")
    return _create_test_agent(token)


def _get_last_assistant_message(agent: Agent) -> str:
    messages = agent.message_processor.get_messages()
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage):
            return msg.message
    return ""


async def test_pure_conversation():
    async def try_once():
        agent = await _get_agent()
        await agent.message_processor.add_new_message(
            UserMessage("Say hello in one word")
        )
        await agent.generate_response()
        response = _get_last_assistant_message(agent)
        return response if response else None

    await retry_llm_call(try_once)


async def test_tool_calling_loop():
    async def try_once():
        agent = await _get_agent()
        await agent.message_processor.add_new_message(
            UserMessage("Use the get_weather tool for Tokyo, then tell me the result")
        )
        for _ in range(3):
            await agent.generate_response()
        response = _get_last_assistant_message(agent)
        return response if response else None

    await retry_llm_call(try_once)


async def test_context_management():
    async def try_once():
        agent = await _get_agent()

        await agent.message_processor.add_new_message(
            UserMessage("My secret code is BLUEBIRD. Remember it.")
        )
        await agent.generate_response()

        await agent.message_processor.add_new_message(
            UserMessage("What is my secret code?")
        )
        await agent.generate_response()

        response = _get_last_assistant_message(agent)
        return response if "BLUEBIRD" in response.upper() else None

    await retry_llm_call(try_once)
