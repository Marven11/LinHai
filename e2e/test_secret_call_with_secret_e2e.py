import tempfile
import shutil
import unittest
import unittest.mock
from pathlib import Path

from linhai.base import (
    AssistantMessage,
    OpenAiToolResultMessage,
    UserMessage,
)
from linhai.llm import OpenAiAnswer
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.agent.main import Agent
from linhai.tool.main import ToolManager
from linhai.config import ToolConfig
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.base import ToolSet, ToolArgInfo, SuccessfulToolResult
from linhai.task_supervisor import PlainTaskSupervisor
from linhai.secret import (
    SecretInfo,
    _create_call_with_secret_toolset,
)


def _make_fake_answer(registry, content, tool_calls_data):
    async def empty_stream():
        return
        yield

    answer = OpenAiAnswer(stream=empty_stream(), registry=registry)
    answer.content = content
    if tool_calls_data:
        answer._openai_toolcall_parts = {i: tc for i, tc in enumerate(tool_calls_data)}
    return answer


class FakeOpenAiLlm:
    def __init__(self, registry, responses):
        self.registry = registry
        self.responses = responses
        self._idx = 0

    def get_custom_toolcall_format(self):
        return False

    def get_token_limit(self):
        return 65536

    def get_name(self):
        return "fake_openai"

    def get_explicit_cache_info(self):
        return None

    def support_image(self):
        return False

    def get_compress_threshold(self):
        return None

    def get_description(self):
        return "fake openai for testing"

    async def answer_stream(self, history):
        answer = self.responses[self._idx]
        self._idx += 1
        return answer

    async def reconnect(self):
        pass


def _make_echo_toolset():
    toolset = ToolSet()

    @toolset.register_tool(
        name="echo",
        desc="echo input",
        args={"text": ToolArgInfo(desc="text", type="str")},
        required_args=["text"],
    )
    def echo(text: str):
        return SuccessfulToolResult(content=text)

    return toolset


def _make_secrets_dict():
    return {
        "TEST_PASSWORD": {
            "value": "secret123",
            "description": "test password",
            "disabled_in_toolcall_argument": False,
        },
    }


def _setup_registry(registry, fake_llm, secrets_dict, tmpdir):
    registry.register_queue("parsed_agent_answer")
    registry.register_queue("ui_log")
    registry.register_queue("ui_answer_text")
    registry.register_queue("ui_toolcall")

    llm_manager = LlmManager(
        registry=registry,
        llms=[fake_llm],
        default_llm_name="fake_openai",
        llm_fallback_map={"fake_openai": None},
        llm_fallback_duration_map={"fake_openai": 120},
    )

    mock_mcp = unittest.mock.MagicMock(spec=MCPConnector)
    mock_mcp.get_toolsets = unittest.mock.MagicMock(return_value=[])
    tool_manager = ToolManager(registry, ToolConfig(config={}), mock_mcp)

    echo_toolset = _make_echo_toolset()
    tool_manager.register_toolset("test", echo_toolset)
    tool_manager._toolsets["test"] = echo_toolset
    tool_manager._enabled["test"] = True

    secret_toolset = _create_call_with_secret_toolset(secrets_dict, registry)
    tool_manager.register_toolset("secret_wrapper", secret_toolset)
    tool_manager._toolsets["secret_wrapper"] = secret_toolset
    tool_manager._enabled["secret_wrapper"] = True

    registry.register_member("task_supervisor", PlainTaskSupervisor())
    registry.register_member("conversation_folder", tmpdir)
    registry.register_member("secrets_dict", secrets_dict)

    return llm_manager, tool_manager


class TestCallWithSecretE2e(unittest.IsolatedAsyncioTestCase):
    async def test_replaces_placeholder_and_masks_result(self):
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "secret_intercepted").mkdir()
        try:
            registry = Registry()
            secrets_dict = _make_secrets_dict()

            response = _make_fake_answer(
                registry,
                "calling echo with secret",
                [
                    {
                        "id": "call_1",
                        "name": "call_with_secret",
                        "args": '{"tool_name": "echo", "tool_arguments": {"text": "pass is <$TEST_PASSWORD$>"}, "with_secret": ["TEST_PASSWORD"]}',
                    }
                ],
            )
            fake_llm = FakeOpenAiLlm(registry, [response])
            llm_manager, tool_manager = _setup_registry(
                registry, fake_llm, secrets_dict, tmpdir
            )

            echo_ts = _make_echo_toolset()
            secret_ts = _create_call_with_secret_toolset(secrets_dict, registry)

            agent = Agent(
                llm_manager=llm_manager,
                compress_threshold=65536,
                registry=registry,
                pinned_messages=[],
                max_toolcall_token_in_round=100000,
            )
            agent.toolcall_processor._register_llm_tools(echo_ts)
            agent.toolcall_processor._register_llm_tools(secret_ts)
            agent.toolcall_processor._register_dummy_tools(echo_ts)
            agent.toolcall_processor._register_dummy_tools(secret_ts)

            await agent.message_processor.add_new_message(
                UserMessage(message="echo secret")
            )
            await agent.generate_response()

            messages = agent.message_processor.get_messages()
            tool_results = [
                m for m in messages if isinstance(m, OpenAiToolResultMessage)
            ]
            self.assertEqual(len(tool_results), 1)
            self.assertNotIn("secret123", tool_results[0].content)
        finally:
            shutil.rmtree(tmpdir)

    async def test_add_rule_title_no_underscores(self):
        from linhai.base import SystemMessage
        from linhai.secret import _CALL_WITH_SECRET_RULE, get_available_secrets_message

        registry = Registry()
        system_message = SystemMessage(registry)
        secrets_dict = _make_secrets_dict()
        secrets_msg = get_available_secrets_message(secrets_dict)
        rule_content = _CALL_WITH_SECRET_RULE.format(secrets_list=secrets_msg)

        system_message.add_rule("CALL WITH SECRET", rule_content)

        content = system_message.get_content()
        self.assertIn("call_with_secret", content)


if __name__ == "__main__":
    unittest.main()
