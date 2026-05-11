import unittest
import unittest.mock
import asyncio
from pathlib import Path

from linhai.base import AnswerToken, AssistantMessage, SystemMessage
from linhai.llm import OpenAiAnswer
from linhai.llm_manager import LlmManager
from linhai.registry import Registry
from linhai.agent.main import Agent
from linhai.tool.main import ToolManager
from linhai.config import ToolConfig
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.base import ToolSet, ToolArgInfo, SuccessfulToolResult
from linhai.task_supervisor import PlainTaskSupervisor


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


def _make_toolset():
    toolset = ToolSet()

    @toolset.register_tool(
        name="add",
        desc="add two numbers",
        args={
            "a": ToolArgInfo(desc="first", type="int"),
            "b": ToolArgInfo(desc="second", type="int"),
        },
        required_args=["a", "b"],
    )
    def add(a: int, b: int):
        return SuccessfulToolResult(content=str(a + b))

    @toolset.register_tool(
        name="echo",
        desc="echo input",
        args={"text": ToolArgInfo(desc="text", type="str")},
        required_args=["text"],
    )
    def echo(text: str):
        return SuccessfulToolResult(content=text)

    return toolset


def _setup_registry(registry, fake_llm, toolset):
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
    tool_manager = ToolManager(registry, ToolConfig(), mock_mcp)
    tool_manager.register_toolset("test", toolset)
    tool_manager._toolsets["test"] = toolset
    tool_manager._enabled["test"] = True

    registry.register_member("task_supervisor", PlainTaskSupervisor())
    registry.register_member("conversation_folder", Path("/tmp/test_e2e"))

    return llm_manager, tool_manager


class TestOpenaiToolcallE2eSingleTool(unittest.IsolatedAsyncioTestCase):
    async def test_single_openai_tool_call(self):
        registry = Registry()

        response = _make_fake_answer(
            registry,
            "I will add for you",
            [{"id": "call_1", "name": "add", "args": '{"a": 3, "b": 5}'}],
        )
        fake_llm = FakeOpenAiLlm(registry, [response])
        toolset = _make_toolset()
        llm_manager, tool_manager = _setup_registry(registry, fake_llm, toolset)

        agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=65536,
            registry=registry,
            pinned_messages=[],
            max_toolcall_token_in_round=100000,
        )
        agent.toolcall_processor._register_llm_tools(toolset)
        agent.toolcall_processor._register_dummy_tools(toolset)

        from linhai.base import UserMessage

        await agent.message_processor.add_new_message(
            UserMessage(message="add 3 and 5")
        )

        await agent.generate_response()

        messages = agent.message_processor.get_messages()
        from linhai.base import OpenAiToolResultMessage

        tool_results = [m for m in messages if isinstance(m, OpenAiToolResultMessage)]
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(tool_results[0].tool_call_id, "call_1")
        self.assertEqual(tool_results[0].content, "8")


class TestOpenaiToolcallE2eMultiTool(unittest.IsolatedAsyncioTestCase):
    async def test_multiple_openai_tool_calls(self):
        registry = Registry()

        response = _make_fake_answer(
            registry,
            "doing two things",
            [
                {"id": "call_a", "name": "add", "args": '{"a": 1, "b": 2}'},
                {"id": "call_b", "name": "echo", "args": '{"text": "hello"}'},
            ],
        )
        fake_llm = FakeOpenAiLlm(registry, [response])
        toolset = _make_toolset()
        llm_manager, tool_manager = _setup_registry(registry, fake_llm, toolset)

        agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=65536,
            registry=registry,
            pinned_messages=[],
            max_toolcall_token_in_round=100000,
        )
        agent.toolcall_processor._register_llm_tools(toolset)
        agent.toolcall_processor._register_dummy_tools(toolset)

        from linhai.base import UserMessage

        await agent.message_processor.add_new_message(UserMessage(message="do stuff"))

        await agent.generate_response()

        messages = agent.message_processor.get_messages()
        from linhai.base import OpenAiToolResultMessage

        tool_results = [m for m in messages if isinstance(m, OpenAiToolResultMessage)]
        self.assertEqual(len(tool_results), 2)
        self.assertEqual(tool_results[0].tool_call_id, "call_a")
        self.assertEqual(tool_results[0].content, "3")
        self.assertEqual(tool_results[1].tool_call_id, "call_b")
        self.assertEqual(tool_results[1].content, "hello")


class TestOpenaiToolcallE2eMultiTurn(unittest.IsolatedAsyncioTestCase):
    async def test_multi_turn_tool_calling(self):
        registry = Registry()

        round1 = _make_fake_answer(
            registry,
            "first call",
            [{"id": "call_r1", "name": "add", "args": '{"a": 10, "b": 20}'}],
        )
        round2 = _make_fake_answer(
            registry,
            "the answer is 30",
            None,
        )
        fake_llm = FakeOpenAiLlm(registry, [round1, round2])
        toolset = _make_toolset()
        llm_manager, tool_manager = _setup_registry(registry, fake_llm, toolset)

        agent = Agent(
            llm_manager=llm_manager,
            compress_threshold=65536,
            registry=registry,
            pinned_messages=[],
            max_toolcall_token_in_round=100000,
        )
        agent.toolcall_processor._register_llm_tools(toolset)
        agent.toolcall_processor._register_dummy_tools(toolset)

        from linhai.base import UserMessage

        await agent.message_processor.add_new_message(
            UserMessage(message="add 10 and 20")
        )

        await agent.generate_response()

        messages = agent.message_processor.get_messages()
        from linhai.base import OpenAiToolResultMessage

        tool_results = [m for m in messages if isinstance(m, OpenAiToolResultMessage)]
        self.assertEqual(len(tool_results), 1)
        self.assertEqual(tool_results[0].content, "30")

        await agent.generate_response()

        messages = agent.message_processor.get_messages()
        assistants = [m for m in messages if isinstance(m, AssistantMessage)]
        self.assertGreaterEqual(len(assistants), 2)


if __name__ == "__main__":
    unittest.main()
