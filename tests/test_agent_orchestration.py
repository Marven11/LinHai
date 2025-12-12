"""AgentMessageOrchestration类的单元测试。"""

import unittest
from unittest.mock import Mock, patch

from linhai.agent.orchestration import AgentMessageOrchestration
from linhai.agent.message import AgentMessage
from linhai.llm import UserMessage, AssistantMessage, SystemMessage
from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat


class TestAgentMessageOrchestration(unittest.IsolatedAsyncioTestCase):
    """AgentMessageOrchestration类的测试用例。"""

    def setUp(self):
        """设置测试环境。"""
        group_chat = GroupChat()
        # 注册一个mock的lifecycle以避免RuntimeError
        from linhai.agent.lifecycle import Lifecycle

        mock_lifecycle = Mock(spec=Lifecycle)
        mock_lifecycle.register_after_working = Mock()
        group_chat.register_member("lifecycle", mock_lifecycle)

        self.init_messages = [
            SystemMessage(
                template="System message",
                group_chat=group_chat,
            ),
            UserMessage(message="Initial message"),
        ]
        self.message_processor = AgentMessage(group_chat, self.init_messages)
        self.orchestration = AgentMessageOrchestration(
            group_chat, self.message_processor
        )

    def test_mark_messages_as_garbage(self):
        """测试标记消息为垃圾。"""
        large_msg = RuntimeMessage("Large content" * 1000)
        message_id = self.orchestration.record_large_message(large_msg, "large content")
        self.message_processor.append_message(large_msg)

        result = self.orchestration.mark_messages_as_garbage([message_id])

        self.assertIn("成功标记 1 条消息", result)
        self.assertIn(f"ID为{message_id}的消息已被标记为垃圾", result)
        self.assertIn(message_id, self.orchestration.garbage_message_ids)

    def test_mark_messages_as_garbage_not_found(self):
        """测试标记不存在的消息为垃圾。"""
        result = self.orchestration.mark_messages_as_garbage(["nonexistent_id"])

        self.assertIn("以下ID不存在: nonexistent_id", result)

    def test_record_large_message(self):
        """测试记录大消息。"""
        large_msg = RuntimeMessage("Large content")
        message_id = self.orchestration.record_large_message(large_msg, "large content")

        self.assertIn(message_id, self.orchestration.large_messages)
        self.assertEqual(self.orchestration.large_messages[message_id], large_msg)

    async def test_thanox_history(self):
        """测试随机删除历史消息。"""
        for i in range(10):
            self.message_processor.append_message(UserMessage(message=f"Message {i}"))

        original_count = len(self.message_processor.get_messages())
        result = await self.orchestration.thanox_history()

        self.assertIn("thanox_history", result)
        self.assertLess(len(self.message_processor.get_messages()), original_count)

    async def test_thanox_history_insufficient_messages(self):
        """测试消息不足时的不删除。"""
        result = await self.orchestration.thanox_history()
        self.assertEqual(result, "消息数量不足，无需删除")

    def test_add_soft_threshold_notification(self):
        """测试添加软限制通知。"""
        threshold_info = (100000, 60000, 40000, 0.8)
        # 添加一个大消息，以便在红灯状态下可以显示大消息信息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.record_large_message(large_msg, "large content")
        self.message_processor.append_message(large_msg)

        # 测试时先重置压缩工具调用状态，然后调用add_soft_threshold_notification
        self.orchestration.compress_tool_called_in_last_response = False
        self.orchestration.add_soft_threshold_notification(threshold_info)

        self.assertEqual(
            len(self.message_processor.messages), 4
        )  # 初始2条 + 1条大消息 + 1条通知
        self.assertIn("黄灯状态", str(self.message_processor.messages[-1]))
        self.assertIn("Token用量", str(self.message_processor.messages[-1]))

    def test_add_soft_threshold_notification_with_compress_tool(self):
        """测试压缩工具调用后不添加通知。"""
        threshold_info = (100000, 60000, 40000, 0.6)
        # 添加一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        self.orchestration.record_large_message(large_msg, "large content")
        self.message_processor.append_message(large_msg)

        # 测试压缩工具调用后不添加通知
        self.orchestration.compress_tool_called_in_last_response = True
        self.orchestration.add_soft_threshold_notification(threshold_info)

        self.assertEqual(
            len(self.message_processor.messages), 3
        )  # 初始2条 + 1条大消息，没有通知

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

    def test_get_status_display_piece(self):
        """测试获取状态显示片段。"""
        self.message_processor.append_message(RuntimeMessage("test"))

        # 记录一个大消息
        large_msg = RuntimeMessage("Large content" * 1000)
        message_id = self.orchestration.record_large_message(large_msg, "large content")
        self.message_processor.append_message(large_msg)

        # 标记为垃圾
        self.orchestration.mark_messages_as_garbage([message_id])

        # 测试不使用nerd font
        pieces = self.orchestration.get_status_display_pieces(use_nerd_font=False)
        self.assertIsInstance(pieces, list)
        self.assertGreater(len(pieces), 0)
        # 应该包含消息计数 - 格式已改为 '4 msgs', '1 large', '1 garbage'
        for piece in pieces:
            if "msgs" in piece:
                self.assertIn("4", piece)  # 消息数量
            elif "large" in piece:
                self.assertIn("1", piece)  # 大消息数量
            elif "garbage" in piece:
                self.assertIn("1", piece)  # 垃圾消息数量

        # 测试使用nerd font
        nerd_pieces = self.orchestration.get_status_display_pieces(use_nerd_font=True)
        self.assertIsInstance(nerd_pieces, list)
        self.assertGreater(len(nerd_pieces), 0)
        # nerd字体使用图标，所以我们检查是否包含消息数量
        for piece in nerd_pieces:
            if "\uf27a" in piece:  # 消息图标
                self.assertIn("4", piece)  # 消息数量
            elif "\uf1c0" in piece:  # 大消息图标
                self.assertIn("1", piece)
            elif "\uea81" in piece:  # 垃圾图标
                self.assertIn("1", piece)


if __name__ == "__main__":
    unittest.main()
