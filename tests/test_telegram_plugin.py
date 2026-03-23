import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.plugin.telegram import TelegramPlugin
from linhai.config import TelegramConfig
from linhai.telegram import TelegramMessage


class TestTelegramPlugin(unittest.TestCase):
    """TelegramPlugin单元测试。"""

    def setUp(self):
        self.group_chat = Mock()
        self.group_chat.get_member_typechecked = Mock()
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.group_chat.get_member_typechecked.return_value = self.agent
        self.telegram_config = TelegramConfig(
            bot_token="test_token", default_chat_id="test_chat_id"
        )

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        self.assertEqual(plugin.config, self.telegram_config)
        self.assertEqual(len(plugin.sent_hashes), 0)
        self.assertIsNone(plugin._bot)
        self.assertIsNone(plugin._application)
        self.assertFalse(plugin._running)

    async def test_after_segment_finished_normal(self):
        """测试处理normal segment。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock()

        segment = {"segment_type": "normal", "content": "test content"}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.sent_hashes), 1)
        plugin._bot.send_message.assert_called_once()

        segment = {"segment_type": "normal", "content": "test content"}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.sent_hashes), 1)
        plugin._bot.send_message.assert_called_once()

    async def test_after_segment_finished_reasoning(self):
        """测试不处理reasoning segment。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock()

        segment = {"segment_type": "reasoning", "content": "test content"}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.sent_hashes), 0)
        plugin._bot.send_message.assert_not_called()

    async def test_after_segment_finished_empty_content(self):
        """测试不处理空内容的segment。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock()

        segment = {"segment_type": "normal", "content": "   "}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.sent_hashes), 0)
        plugin._bot.send_message.assert_not_called()

    async def test_after_segment_finished_duplicate(self):
        """测试去重逻辑。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock()

        segment = {"segment_type": "normal", "content": "test content"}
        await plugin.after_segment_finished(None, segment)
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.sent_hashes), 1)
        self.assertEqual(plugin._bot.send_message.call_count, 1)

    async def test_send_to_telegram_without_app(self):
        """测试在app未初始化时发送消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        with patch("linhai.plugin.telegram.Bot") as mock_bot_class:
            mock_bot = Mock()
            mock_bot.send_message = AsyncMock()
            mock_bot_class.return_value = mock_bot

            await plugin._send_to_telegram("test message")

            mock_bot_class.assert_called_once_with(token="test_token")
            mock_bot.send_message.assert_called_once()

    async def test_send_to_telegram_with_bot(self):
        """测试在bot已初始化时发送消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock()

        await plugin._send_to_telegram("test message")

        plugin._bot.send_message.assert_called_once()

    async def test_send_to_telegram_exception(self):
        """测试发送消息失败时的异常处理。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock(side_effect=Exception("Send failed"))

        await plugin._send_to_telegram("test message")

    async def test_handle_telegram_message_valid(self):
        """测试处理有效的telegram消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"
        mock_update.message.message_id = 123

        await plugin._handle_telegram_message(mock_update, None)

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(call_args, TelegramMessage)
        self.assertEqual(call_args.content, "Hello")

    async def test_handle_telegram_message_invalid_chat_id(self):
        """测试处理来自未授权chat_id的消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "invalid_chat_id"
        mock_update.message.text = "Hello"

        await plugin._handle_telegram_message(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_handle_telegram_message_no_message(self):
        """测试处理没有message字段的update。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        mock_update = Mock()
        mock_update.message = None

        await plugin._handle_telegram_message(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_handle_telegram_message_empty_text(self):
        """测试处理空文本消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = None

        await plugin._handle_telegram_message(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_handle_telegram_message_exception(self):
        """测试处理telegram消息时的异常处理。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        self.group_chat.get_member_typechecked.side_effect = Exception(
            "Agent not found"
        )

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"

        await plugin._handle_telegram_message(mock_update, None)

    async def test_before_agent_loop(self):
        """测试Agent循环开始时启动telegram bot。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._application = Mock()
        plugin._application.run_polling = AsyncMock()
        plugin._application.initialize = AsyncMock()
        plugin._application.start = AsyncMock()
        plugin._application.shutdown = AsyncMock()

        with patch("linhai.plugin.telegram.Application") as mock_app_class:
            mock_builder = Mock()
            mock_application = Mock()
            mock_application.initialize = AsyncMock()
            mock_application.start = AsyncMock()
            mock_application.shutdown = AsyncMock()
            mock_application.run_polling = AsyncMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = mock_application
            mock_app_class.builder.return_value = mock_builder

            await plugin.before_agent_loop(None)

            self.assertTrue(plugin._running)

    async def test_before_agent_loop_already_running(self):
        """测试bot已在运行时不重复启动。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._running = True
        plugin._application = Mock()
        plugin._application.initialize = AsyncMock()
        plugin._application.start = AsyncMock()

        await plugin.before_agent_loop(None)

        plugin._application.initialize.assert_not_called()
        plugin._application.start.assert_not_called()

    async def test_shutdown(self):
        """测试关闭telegram bot。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._application = Mock()
        plugin._application.stop = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._running = True

        await plugin.shutdown()

        self.assertFalse(plugin._running)
        plugin._application.stop.assert_called_once()
        plugin._application.shutdown.assert_called_once()

    async def test_shutdown_not_running(self):
        """测试bot未运行时不执行关闭。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._application = Mock()
        plugin._application.stop = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._running = False

        await plugin.shutdown()

        plugin._application.stop.assert_not_called()
        plugin._application.shutdown.assert_not_called()

    def test_register(self):
        """测试注册到Lifecycle。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        mock_lifecycle = Mock()

        plugin.register(mock_lifecycle)

        mock_lifecycle.register_after_segment_finished.assert_called_once()
        mock_lifecycle.register_before_agent_loop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
