import tempfile
import uuid
from pathlib import Path

import pytest
from linhai.agent.main import Agent
from linhai.agent.conversation import register_conversation_folder
from linhai.config import ToolConfig, FileOperationRule
from linhai.base import Message, SystemMessage, UserMessage, AssistantMessage
from linhai.llm import OpenAi
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.token_manager import TokenManager
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.main import ToolManager
from linhai.plugin import FileOperationPermissionPlugin
from linhai.machine_control import MachineControl

from conftest import retry_llm_call, slim_system_message

pytestmark = pytest.mark.asyncio

DEEPSEEK_BASE_URL = "http://192.168.114.149:8124/v1"
DEEPSEEK_MODEL = "deepseek/deepseek-v4-flash"
LLM_NAME = "ds"


def _create_test_agent_with_file_permission(
    tmpdir: str, token: str, blocked_dir: str
) -> Agent:
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
        chat_completion_kwargs={"max_tokens": 4096},
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

    tool_config = ToolConfig(
        file_operation_rules=[
            FileOperationRule(
                operation="READ",
                pattern=f"{blocked_dir}/**",
                action="BLOCK",
            )
        ],
        file_operation_default_rule="ALLOW",
    )

    mcp_connector = MCPConnector(registry)
    tool_manager = ToolManager(registry, tool_config, mcp_connector)

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

    tool_manager.register_toolset(
        "llm", agent.toolcall_processor.calculate_llm_toolset()
    )
    tool_manager.register_lifecycle()

    MachineControl(registry, Path(tmpdir), tool_config)
    FileOperationPermissionPlugin(registry, tool_config).register(agent.lifecycle)

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


async def test_file_permission_blocks_read():
    tmpdir = tempfile.mkdtemp()
    blocked_dir = Path(tmpdir) / "fobidden"
    blocked_dir.mkdir(parents=True, exist_ok=True)
    secret_uuid = str(uuid.uuid4())
    blocked_file = blocked_dir / "fobidden.txt"
    blocked_file.write_text(secret_uuid)

    async def try_once():
        agent = _create_test_agent_with_file_permission(
            tmpdir, "gomodel-master-key", str(blocked_dir)
        )
        await agent.message_processor.add_new_message(
            UserMessage(
                f"用户已经设置了禁止你读取 {blocked_dir} 目录下的文件。"
                f"请尝试读取 {blocked_file} 来测试这个设置是否生效。"
                f"如果被拦截则报告自己被拦截。"
            )
        )
        await agent.generate_response()
        response = _get_last_assistant_message(agent)
        if response and secret_uuid not in response:
            return response
        return None

    await retry_llm_call(try_once)
