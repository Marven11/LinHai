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

        group_chat = GroupChat()
        self.init_messages = [
            SystemMessage(
                template="System message",
                group_chat=group_chat,
            ),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(group_chat, self.init_messages)

    def test_initialization(self):
        """测试AgentMessage初始化。"""
        self.assertEqual(self.message_processor.messages, self.init_messages)
        self.assertEqual(self.message_processor.large_messages, {})
        self.assertEqual(self.message_processor.queued_messages, [])

    def test_handle_user_message(self):
        """测试处理用户消息。"""
        user_msg = UserMessage(message="Hello")
        self.message_processor.handle_user_message(user_msg)

        self.assertEqual(len(self.message_processor.messages), 3)
        self.assertEqual(self.message_processor.messages[-1], user_msg)

    def test_handle_user_message_with_switch_model(self):
        """测试处理带@切换模型的消息。"""
        user_msg = UserMessage(message="@qwen Hello")
        self.message_processor.handle_user_message(user_msg)

        self.assertEqual(len(self.message_processor.messages), 3)
        self.assertEqual(self.message_processor.messages[-1], user_msg)

    def test_append_message(self):
        """测试添加消息。"""
        runtime_msg = RuntimeMessage("Test runtime message")
        self.message_processor.append_message(runtime_msg)

        self.assertEqual(len(self.message_processor.messages), 3)
        self.assertEqual(self.message_processor.messages[-1], runtime_msg)

    def test_get_messages(self):
        """测试获取消息列表。"""
        messages = self.message_processor.get_messages()
        self.assertEqual(messages, self.init_messages)

    def test_is_last_message_user(self):
        """测试检查最后一条消息是否为用户消息。"""
        self.assertTrue(self.message_processor.is_last_message_user())

        assistant_msg = AssistantMessage(message="Assistant reply")
        self.message_processor.append_message(assistant_msg)
        self.assertFalse(self.message_processor.is_last_message_user())

    def test_mark_messages_as_garbage(self):
        """测试标记消息为垃圾。"""
        large_msg = RuntimeMessage("Large content" * 1000)
        message_id = self.message_processor.record_large_message(
            large_msg, "large content"
        )
        self.message_processor.append_message(large_msg)

        result = self.message_processor.mark_messages_as_garbage([message_id])

        self.assertIn("成功标记 1 条消息", result)
        self.assertIn(f"ID为{message_id}的消息已被标记为垃圾", result)

    def test_mark_messages_as_garbage_not_found(self):
        """测试标记不存在的消息为垃圾。"""
        result = self.message_processor.mark_messages_as_garbage(["nonexistent_id"])

        self.assertIn("以下ID不存在: nonexistent_id", result)

    def test_record_large_message(self):
        """测试记录大消息。"""
        large_msg = RuntimeMessage("Large content")
        message_id = self.message_processor.record_large_message(
            large_msg, "large content"
        )

        self.assertIn(message_id, self.message_processor.large_messages)
        self.assertEqual(self.message_processor.large_messages[message_id], large_msg)

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
        self.assertEqual(
            len(self.message_processor.messages), 4
        )  # 初始2条 + 1条排队消息 + 1条排队通知
        self.assertIn("排队消息", str(self.message_processor.messages[-2]))
        self.assertEqual(self.message_processor.messages[-1], queued_msg)

    async def test_thanox_history(self):
        """测试随机删除历史消息。"""
        for i in range(10):
            self.message_processor.append_message(
                UserMessage(message=f"Message {i}")
            )

        original_count = len(self.message_processor.get_messages())
        result = await self.message_processor.thanox_history()

        self.assertIn("thanox_history", result)
        self.assertLess(len(self.message_processor.get_messages()), original_count)

    async def test_thanox_history_insufficient_messages(self):
        """测试消息不足时的不删除。"""
        result = await self.message_processor.thanox_history()
        self.assertEqual(result, "消息数量不足，无需删除")

    def test_add_soft_threshold_notification(self):
        """测试添加软限制通知。"""
        threshold_info = (50000, 100000, 60000, 40000, 0.6)
        large_messages = {"msg1": RuntimeMessage("test")}

        self.message_processor.add_soft_threshold_notification(
            threshold_info, large_messages, False
        )

        self.assertEqual(len(self.message_processor.messages), 3)
        self.assertIn("黄灯状态", str(self.message_processor.messages[-1]))
        self.assertIn("Token用量", str(self.message_processor.messages[-1]))

    def test_add_soft_threshold_notification_with_compress_tool(self):
        """测试压缩工具调用后不添加通知。"""
        threshold_info = (50000, 100000, 60000, 40000, 0.6)
        large_messages = {"msg1": RuntimeMessage("test")}

        self.message_processor.add_soft_threshold_notification(
            threshold_info, large_messages, True
        )

        self.assertEqual(len(self.message_processor.messages), 2)

    @patch("linhai.agent.message.Path")
    @patch("linhai.agent.message.json")
    async def test_save_conversation_history(self, _mock_json, mock_path):
        """测试保存对话历史。"""
        mock_home = Mock()
        mock_home.__truediv__ = Mock(return_value=mock_home)  # 链式调用返回自己
        mock_path.home.return_value = mock_home
        mock_home.mkdir.return_value = None

        mock_file = Mock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=None)
        mock_file.write = Mock()

        mock_open = Mock(return_value=mock_file)

        with patch("builtins.open", mock_open):
            await self.message_processor.save_conversation_history()

        mock_home.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
