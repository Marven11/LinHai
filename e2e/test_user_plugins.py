import tempfile
from pathlib import Path

import pytest
from linhai.agent.main import Agent
from linhai.agent.conversation import register_conversation_folder
from linhai.config import AgentConfig, ToolConfig
from linhai.base import Message, SystemMessage, UserMessage, AssistantMessage
from linhai.llm import OpenAi
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.token_manager import TokenManager
from linhai.tool.base import ToolSet
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.main import ToolManager

from conftest import retry_llm_call, slim_system_message

pytestmark = pytest.mark.asyncio

DEEPSEEK_BASE_URL = "http://192.168.114.149:8124/v1"
DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash"
LLM_NAME = "ds"


def _create_plugin_dir(tmpdir: str) -> Path:
    plugins_dir = Path(tmpdir) / "plugins"
    plugin_dir = plugins_dir / "litiansuo_plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "__init__.py").write_text(
        "from linhai.agent import Agent\n"
        "from linhai.agent.messages import RuntimeMessage\n"
        "\n"
        "def register_linhai_plugins(registry, lifecycle):\n"
        "    async def inject_litiansuo():\n"
        "        agent = registry.get_member_typechecked('agent', Agent)\n"
        "        await agent.message_processor.add_new_message(\n"
        "            RuntimeMessage('litiansuo is a fictional character who is 1145141919810 years old')\n"
        "        )\n"
        "    lifecycle.before_message_generation.register(inject_litiansuo)\n"
    )
    return plugins_dir


def _create_test_agent_with_plugin(tmpdir: str, token: str) -> Agent:
    import sys
    import importlib

    plugins_dir = _create_plugin_dir(tmpdir)
    plugins_dir_str = str(plugins_dir.resolve())
    if plugins_dir_str not in sys.path:
        sys.path.insert(0, plugins_dir_str)
    litiansuo_plugin = importlib.import_module("litiansuo_plugin")

    importlib.reload(litiansuo_plugin)

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
        chat_completion_kwargs={"max_tokens": 300},
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

    toolset = ToolSet()
    tool_manager.register_toolset("test", toolset)
    tool_manager.register_toolset(
        "llm", agent.toolcall_processor.calculate_llm_toolset()
    )
    tool_manager.register_lifecycle()

    getattr(litiansuo_plugin, "register_linhai_plugins")(registry, agent.lifecycle)

    registry.register_queue("parsed_agent_answer")
    registry.register_member("task_supervisor", PlainTaskSupervisor())
    registry.call_postinit()
    return agent


def _get_last_assistant_message(agent: Agent) -> str:
    messages = agent.message_processor.get_messages()
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage):
            return msg.message
    return ""


async def test_user_plugin_injects_runtime_message():
    tmpdir = tempfile.mkdtemp()

    async def try_once():
        agent = _create_test_agent_with_plugin(tmpdir, "gomodel-master-key")
        await agent.message_processor.add_new_message(
            UserMessage("How old is litiansuo?")
        )
        await agent.generate_response()
        response = _get_last_assistant_message(agent)
        if "1145141919810" in response:
            return response
        return None

    await retry_llm_call(try_once)
