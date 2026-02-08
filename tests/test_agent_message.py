"""AgentMessage类的单元测试。"""

import unittest
from unittest.mock import Mock, patch


from linhai.agent.message import AgentMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.agent.base import RuntimeMessage


class TestAgentMessage(unittest.IsolatedAsyncioTestCase):
    """AgentMessage类的测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        from linhai.group_chat import GroupChat
        from linhai.tool.main import ToolManager
        from unittest.mock import MagicMock
        from tempfile import TemporaryDirectory
        from pathlib import Path

        group_chat = GroupChat()

        # 注册一个Mock的tool_manager，因为SystemMessage初始化需要它
        mock_tool_manager = MagicMock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        group_chat.register_member("tool_manager", mock_tool_manager)

        # 创建临时目录并注册为conversation_folder，以便save_context可以工作
        self.temp_dir = TemporaryDirectory()
        conversation_dir = Path(self.temp_dir.name)
        group_chat.register_member("conversation_folder", conversation_dir)

        self.pinned_messages = [
            SystemMessage(
                group_chat=group_chat,
            ),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(group_chat, self.pinned_messages)

    def tearDown(self):
        """清理测试环境。"""
        self.temp_dir.cleanup()

    def test_initialization(self):
        """测试AgentMessage初始化。"""
        self.assertEqual(self.message_processor.pinned_messages, self.pinned_messages)
        self.assertEqual(self.message_processor.messages, [])
        self.assertEqual(self.message_processor.queued_messages, [])

    def test_handle_user_message(self):
        """测试处理用户消息。"""
        user_msg = UserMessage(message="Hello")
        self.message_processor.handle_user_message(user_msg)

        # messages列表应包含1条普通消息
        self.assertEqual(len(self.message_processor.messages), 1)
        # get_messages()应返回pinned_messages + messages，总数为3
        self.assertEqual(len(self.message_processor.get_messages()), 3)
        # 最后一条消息应该是添加的用户消息
        self.assertEqual(self.message_processor.get_messages()[-1], user_msg)

    def test_handle_user_message_with_switch_model(self):
        """测试处理带@切换模型的消息。"""
        user_msg = UserMessage(message="@qwen Hello")
        self.message_processor.handle_user_message(user_msg)

        # messages列表应包含1条普通消息
        self.assertEqual(len(self.message_processor.messages), 1)
        # get_messages()应返回pinned_messages + messages，总数为3
        self.assertEqual(len(self.message_processor.get_messages()), 3)
        # 最后一条消息应该是添加的用户消息
        self.assertEqual(self.message_processor.get_messages()[-1], user_msg)

    def test_add_new_message(self):
        """测试添加消息。"""
        runtime_msg = RuntimeMessage("Test runtime message")
        self.message_processor.add_new_message(runtime_msg)

        # messages列表应包含1条普通消息
        self.assertEqual(len(self.message_processor.messages), 1)
        # get_messages()应返回pinned_messages + messages，总数为3
        self.assertEqual(len(self.message_processor.get_messages()), 3)
        # 最后一条消息应该是添加的runtime消息
        self.assertEqual(self.message_processor.get_messages()[-1], runtime_msg)

    def test_get_messages(self):
        """测试获取消息列表。"""
        messages = self.message_processor.get_messages()
        self.assertEqual(messages, self.pinned_messages)

    def test_is_last_message_user(self):
        """测试检查最后一条消息是否为用户消息。"""
        self.assertTrue(self.message_processor.is_last_message_user())

        assistant_msg = AssistantMessage(message="Assistant reply")
        self.message_processor.add_new_message(assistant_msg)
        self.assertFalse(self.message_processor.is_last_message_user())

    def test_add_queued_message(self):
        """测试添加排队消息。"""
        queued_msg = RuntimeMessage("Queued message")
        self.message_processor.add_queued_message(queued_msg)

        self.assertEqual(len(self.message_processor.queued_messages), 1)
        self.assertEqual(self.message_processor.queued_messages[0], queued_msg)

    def test_process_queued_messages(self):
        """测试处理排队消息。"""
        queued_msg = RuntimeMessage("Queued message")
        self.message_processor.add_queued_message(queued_msg)

        self.message_processor.process_queued_messages()

        self.assertEqual(len(self.message_processor.queued_messages), 0)
        # messages列表应包含2条消息: 排队通知和排队消息
        self.assertEqual(len(self.message_processor.messages), 2)
        # get_messages()总数为4: 2条pinned_messages + 2条messages
        self.assertEqual(len(self.message_processor.get_messages()), 4)
        self.assertIn("排队消息", str(self.message_processor.messages[-2]))
        self.assertEqual(self.message_processor.messages[-1], queued_msg)

    @patch("linhai.agent.message.save_context")
    def test_save_context_called_on_add_new_message(self, mock_save_context):
        from pathlib import Path
        runtime_msg = RuntimeMessage("Test runtime message")
        self.message_processor.add_new_message(runtime_msg)
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertIsInstance(call_args[0][0], Path)
        self.assertIsInstance(call_args[0][1], list)
        self.assertEqual(len(call_args[0][1]), 3)

    @patch("linhai.agent.message.save_context")
    async def test_save_context_called_on_replace_messages(self, mock_save_context):
        new_messages = [RuntimeMessage("New message 1"), RuntimeMessage("New message 2")]
        await self.message_processor.replace_messages(new_messages)
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertEqual(len(call_args[0][1]), 4)

    @patch("linhai.agent.message.save_context")
    async def test_save_context_called_on_insert_message(self, mock_save_context):
        runtime_msg = RuntimeMessage("Inserted message")
        await self.message_processor.insert_message(0, runtime_msg)
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertEqual(len(call_args[0][1]), 3)

    @patch("linhai.agent.message.save_context")
    async def test_save_context_called_on_delete_message_range(self, mock_save_context):
        self.message_processor.add_new_message(RuntimeMessage("Msg 1"))
        self.message_processor.add_new_message(RuntimeMessage("Msg 2"))
        mock_save_context.reset_mock()
        await self.message_processor.delete_message_range(0, 0)
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertEqual(len(call_args[0][1]), 3)

    @patch("linhai.agent.message.save_context")
    async def test_save_context_called_on_filter_messages(self, mock_save_context):
        self.message_processor.add_new_message(RuntimeMessage("Msg 1"))
        self.message_processor.add_new_message(RuntimeMessage("Msg 2"))
        mock_save_context.reset_mock()
        await self.message_processor.filter_messages(lambda msg: "1" in str(msg))
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertEqual(len(call_args[0][1]), 3)

    @patch("linhai.agent.message.save_context")
    async def test_save_context_called_on_replace_message(self, mock_save_context):
        old_msg = RuntimeMessage("Message to replace")
        new_msg = RuntimeMessage("New message")
        self.message_processor.add_new_message(old_msg)
        mock_save_context.reset_mock()
        await self.message_processor.replace_message(old_msg, new_msg)
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertEqual(len(call_args[0][1]), 3)

    @patch("linhai.agent.message.save_context")
    def test_save_context_called_on_process_queued_messages(self, mock_save_context):
        queued_msg = RuntimeMessage("Queued message")
        self.message_processor.add_queued_message(queued_msg)
        mock_save_context.reset_mock()
        self.message_processor.process_queued_messages()
        mock_save_context.assert_called_once()
        call_args = mock_save_context.call_args
        self.assertEqual(len(call_args[0]), 2)
        self.assertEqual(len(call_args[0][1]), 4)


if __name__ == "__main__":
    unittest.main()
