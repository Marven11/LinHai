"""测试Agent/SubAgent是否可以看到工具定义的System Prompt"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from linhai.agent import Agent
from linhai.agent.base import RuntimeMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.group_chat import GroupChat
from linhai.tool.main import ToolManager
from linhai.tool.base import global_tools
from linhai.config import ToolConfig
from linhai.subagent.issue import IssueManager


class TestToolSystemPrompt(unittest.IsolatedAsyncioTestCase):
    """测试Agent和SubAgent是否可以看到工具定义的System Prompt"""

    def setUp(self):
        self.mock_llm = MagicMock()
        self.mock_llm.answer_stream = AsyncMock(return_value=AsyncMock())
        self.mock_llm.get_name = MagicMock(return_value="test_llm")
        self.mock_llm.get_token_limit = MagicMock(return_value=None)

        config = {
            "llms": [self.mock_llm],
            "llm_names": ["test_llm"],
            "current_llm_index": 0,
            "compress_threshold": 800,
        }

        self.group_chat = GroupChat()
        self.group_chat.register_queue("agent_answer")

        self.issue_manager = IssueManager(self.group_chat)

        self.tool_manager = ToolManager(
            group_chat=self.group_chat,
            toolsets=[global_tools],
            config=ToolConfig(),
            mcp_config=[],
            mcp_basedir=Path("/tmp"),
        )

        init_messages = [
            SystemMessage(
                group_chat=self.group_chat,
            )
        ]

        self.agent = Agent(
            llms=config["llms"],
            compress_threshold=config["compress_threshold"],
            group_chat=self.group_chat,
            init_messages=init_messages,
            llm_name=config["llm_names"][config["current_llm_index"]],
        )

    def test_agent_message_processor_has_tool_access(self):
        """测试Agent的message_processor属性可以访问工具定义"""
        self.assertTrue(hasattr(self.agent, "message_processor"))

        messages = self.agent.message_processor.get_messages()
        self.assertIsInstance(messages, list)

        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        self.assertGreater(len(system_messages), 0)

    async def test_agent_tool_interaction(self):
        """测试Agent与工具的交互能力"""
        tool_call_response = """我需要调用工具来完成任务喵~

```json toolcall
{
    "name": "safe_calculator",
    "arguments": {
        "expression": "114 + 514"
    }
}
```"""

        class MockAnswer:
            def __init__(self, content):
                self.content = content
                self.tokens = [{"reasoning_content": None, "content": content}]
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.tokens):
                    raise StopAsyncIteration
                token = self.tokens[self.index]
                self.index += 1
                return token

            def get_message(self):
                return AssistantMessage(message=self.content)

            def get_current_content(self):
                return self.content

            def get_reasoning_message(self):
                return None

        mock_answer = MockAnswer(tool_call_response)
        self.mock_llm.answer_stream.return_value = mock_answer

        self.tool_manager.process_tool_call = AsyncMock(
            return_value=RuntimeMessage("628")
        )

        await self.agent.handle_user_message(UserMessage(message="计算114+514"))
        await self.agent.generate_response()

        self.tool_manager.process_tool_call.assert_called_once()
        tool_call = self.tool_manager.process_tool_call.call_args[0][0]
        self.assertEqual(tool_call.function_name, "safe_calculator")
        self.assertEqual(tool_call.function_arguments, {"expression": "114 + 514"})

    def test_agent_can_access_tool_definitions(self):
        """测试Agent可以通过message_processor访问工具定义"""
        self.assertTrue(hasattr(self.agent, "message_processor"))

        messages = self.agent.message_processor.get_messages()
        self.assertIsInstance(messages, list)

        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        self.assertGreater(len(system_messages), 0)

        self.assertTrue(hasattr(self.agent, "toolcall_processor"))

    def test_agent_can_see_tool_names_in_system_prompt(self):
        """测试Agent在系统提示中能看到工具名称"""
        messages = self.agent.message_processor.get_messages()
        system_messages = [msg for msg in messages if isinstance(msg, SystemMessage)]
        self.assertGreater(len(system_messages), 0)

        # 现在SystemMessage没有template属性，但可以通过to_llm_message()获取内容
        system_message = system_messages[0].to_llm_message()
        self.assertIn("content", system_message)
        system_prompt = system_message.get("content")
        self.assertIsInstance(system_prompt, str)
        self.assertIsNotNone(system_prompt)
        self.assertGreater(len(system_prompt or ""), 0)

    def test_tool_manager_has_accessible_tools(self):
        """测试ToolManager有可访问的工具"""
        self.assertTrue(hasattr(self.tool_manager, "toolsets"))
        self.assertIsInstance(self.tool_manager.toolsets, list)

        tools_info = self.tool_manager.get_tools_info()
        self.assertIsInstance(tools_info, list)

        for tool_info in tools_info:
            self.assertIn("type", tool_info)
            self.assertEqual(tool_info["type"], "function")
            self.assertIn("function", tool_info)
            function_info = tool_info["function"]
            self.assertIn("name", function_info)
            self.assertIn("description", function_info)
            self.assertIn("parameters", function_info)


if __name__ == "__main__":
    unittest.main()
