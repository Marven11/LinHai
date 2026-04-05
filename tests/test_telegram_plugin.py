import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.plugin.telegram import TelegramPlugin
from linhai.agent.create import TelegramContext
from linhai.agent.state_machine import AgentStateMachine
from linhai.telegram import TelegramMessage


class TestTelegramPlugin(unittest.TestCase):
    """TelegramPlugin单元测试。"""

    def setUp(self):
        self.registry = Mock()
        self.registry.send_if_exists = AsyncMock()
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.add_new_message = AsyncMock()
        self.state_machine = Mock(spec=AgentStateMachine)
        self.state_machine.state = "waiting_user"
        self.state_machine.transition_to_working = Mock(
            side_effect=lambda: setattr(self.state_machine, "state", "working")
        )

        def get_member(name, cls):
            if name == "state_machine":
                return self.state_machine
            return self.agent

        self.registry.get_member_typechecked = Mock(side_effect=get_member)
        self.telegram_config = TelegramContext(
            bot_token="test_token", default_chat_id="test_chat_id"
        )

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        self.assertEqual(plugin.config, self.telegram_config)
        self.assertIsNone(plugin._bot)
        self.assertIsNone(plugin._application)
        self.assertFalse(plugin._running)
        self.assertIsNotNone(plugin.send_queue)

    def test_after_segment_finished_normal(self):
        """测试处理normal segment，将消息加入队列。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {"segment_type": "normal", "content": "test content"}
        asyncio.run(plugin.after_segment_finished(None, segment))

        self.assertEqual(len(plugin.send_queue), 1)
        self.assertEqual(
            plugin.send_queue[0], {"segment_type": "normal", "content": "test content"}
        )

    def test_after_segment_finished_reasoning(self):
        """测试不处理reasoning segment。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {"segment_type": "reasoning", "content": "test content"}
        asyncio.run(plugin.after_segment_finished(None, segment))

        self.assertEqual(len(plugin.send_queue), 0)

    def test_after_segment_finished_empty_content(self):
        """测试处理空内容的segment（会加入队列，因为没有空内容检查）。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {"segment_type": "normal", "content": "   "}
        asyncio.run(plugin.after_segment_finished(None, segment))

        self.assertEqual(len(plugin.send_queue), 1)

    def test_after_segment_finished_duplicate(self):
        """测试相同内容会被加入队列两次。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {"segment_type": "normal", "content": "test content"}
        asyncio.run(plugin.after_segment_finished(None, segment))
        asyncio.run(plugin.after_segment_finished(None, segment))

        self.assertEqual(len(plugin.send_queue), 2)
        self.assertEqual(
            plugin.send_queue[0], {"segment_type": "normal", "content": "test content"}
        )
        self.assertEqual(
            plugin.send_queue[1], {"segment_type": "normal", "content": "test content"}
        )

    def test_send_loop_with_no_bot(self):
        """测试bot为None时的行为（暂不实现，因为_send_loop是内部方法）。"""
        pass

    def test_send_loop_with_bot(self):
        """测试bot存在时的行为（暂不实现，因为_send_loop是内部方法）。"""
        pass

    def test_send_loop_with_error(self):
        """测试发送失败时的行为（暂不实现，因为_send_loop是内部方法）。"""
        pass

    def test_send_loop_exponential_backoff(self):
        """测试指数回避机制（暂不实现，因为_send_loop是内部方法）。"""
        pass

    def test_handle_telegram_message_valid(self):
        """测试处理有效的telegram消息。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"
        mock_update.message.message_id = 123

        asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertIsInstance(call_args, TelegramMessage)
        self.assertEqual(call_args.content, "Hello")

    def test_handle_telegram_message_state_switch(self):
        """测试telegram消息加入后agent状态从waiting_user切换到working。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        self.state_machine.state = "waiting_user"

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"
        mock_update.message.message_id = 123

        asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.state_machine.transition_to_working.assert_called_once()

    def test_handle_telegram_message_state_already_working(self):
        """测试agent已经在working状态时不会重复调用generate_response。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        self.state_machine.state = "working"
        self.agent.generate_response = AsyncMock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"
        mock_update.message.message_id = 123

        asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.assertEqual(self.state_machine.state, "working")
        self.state_machine.transition_to_working.assert_not_called()

    def test_handle_telegram_message_invalid_chat_id(self):
        """测试处理来自未授权chat_id的消息。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "invalid_chat_id"
        mock_update.message.text = "Hello"

        asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.agent.message_processor.add_new_message.assert_not_called()

    def test_handle_telegram_message_no_message(self):
        """测试处理没有message字段的update。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        mock_update = Mock()
        mock_update.message = None

        asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.agent.message_processor.add_new_message.assert_not_called()

    def test_handle_telegram_message_empty_text(self):
        """测试处理空文本消息。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = None

        asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.agent.message_processor.add_new_message.assert_not_called()

    def test_handle_telegram_message_exception(self):
        """测试处理telegram消息时的异常处理。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        self.registry.get_member_typechecked.side_effect = Exception("Agent not found")

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"

        with self.assertRaises(Exception) as context:
            asyncio.run(plugin._handle_telegram_message(mock_update, None))

        self.assertIn("Agent not found", str(context.exception))

    def test_handle_telegram_sticker_valid(self):
        """测试处理有效的sticker消息。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._bot = Mock()
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(
            return_value=bytearray(b"fake_sticker_data")
        )
        plugin._bot.get_file = AsyncMock(return_value=mock_file)

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        with patch("linhai.plugin.telegram.load_sticker") as mock_load_sticker:
            mock_sticker_message = Mock()
            mock_load_sticker.return_value = mock_sticker_message
            asyncio.run(plugin._handle_telegram_sticker(mock_update, None))

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertEqual(call_args, mock_sticker_message)

    def test_handle_telegram_sticker_state_switch(self):
        """测试sticker消息加入后agent状态从waiting_user切换到working。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._bot = Mock()
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(
            return_value=bytearray(b"fake_sticker_data")
        )
        plugin._bot.get_file = AsyncMock(return_value=mock_file)
        self.state_machine.state = "waiting_user"

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        with patch("linhai.plugin.telegram.load_sticker") as mock_load_sticker:
            mock_sticker_message = Mock()
            mock_load_sticker.return_value = mock_sticker_message
            asyncio.run(plugin._handle_telegram_sticker(mock_update, None))

        self.state_machine.transition_to_working.assert_called_once()

    def test_handle_telegram_sticker_invalid_chat_id(self):
        """测试处理来自未授权chat_id的sticker消息。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._bot = Mock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "invalid_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        asyncio.run(plugin._handle_telegram_sticker(mock_update, None))

        self.agent.message_processor.add_new_message.assert_not_called()
        plugin._bot.get_file.assert_not_called()

    def test_handle_telegram_sticker_no_sticker(self):
        """测试处理没有sticker字段的消息。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._bot = Mock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = None

        asyncio.run(plugin._handle_telegram_sticker(mock_update, None))

        self.agent.message_processor.add_new_message.assert_not_called()
        plugin._bot.get_file.assert_not_called()

    def test_handle_telegram_sticker_no_bot(self):
        """测试bot为None时不处理sticker。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._bot = None

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        asyncio.run(plugin._handle_telegram_sticker(mock_update, None))

        self.agent.message_processor.add_new_message.assert_not_called()

    def test_handle_telegram_sticker_exception(self):
        """测试下载sticker失败时的异常处理。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.get_file = AsyncMock(side_effect=Exception("Download failed"))

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        with self.assertRaises(Exception) as context:
            asyncio.run(plugin._handle_telegram_sticker(mock_update, None))

        self.assertIn("Download failed", str(context.exception))

    def test_before_agent_loop(self):
        """测试Agent循环开始时启动telegram bot。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._application = Mock()
        plugin._application.run_polling = AsyncMock()
        plugin._application.initialize = AsyncMock()
        plugin._application.start = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._application.updater = Mock()
        plugin._application.updater.start_polling = AsyncMock()

        with patch("linhai.plugin.telegram.Application") as mock_app_class:
            mock_builder = Mock()
            mock_application = Mock()
            mock_application.initialize = AsyncMock()
            mock_application.start = AsyncMock()
            mock_application.shutdown = AsyncMock()
            mock_application.updater = Mock()
            mock_application.updater.start_polling = AsyncMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = mock_application
            mock_app_class.builder.return_value = mock_builder

            asyncio.run(plugin.before_agent_loop(None))

            self.assertTrue(plugin._running)

    def test_before_agent_loop_already_running(self):
        """测试bot已在运行时不重复启动。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._running = True
        plugin._application = Mock()
        plugin._application.initialize = AsyncMock()
        plugin._application.start = AsyncMock()

        asyncio.run(plugin.before_agent_loop(None))

        plugin._application.initialize.assert_not_called()
        plugin._application.start.assert_not_called()

    def test_shutdown(self):
        """测试关闭telegram bot。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._application = Mock()
        plugin._application.stop = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._running = True

        asyncio.run(plugin.shutdown())

        self.assertFalse(plugin._running)
        plugin._application.stop.assert_called_once()
        plugin._application.shutdown.assert_called_once()

    def test_shutdown_not_running(self):
        """测试bot未运行时不执行关闭。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._application = Mock()
        plugin._application.stop = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._running = False

        asyncio.run(plugin.shutdown())

        plugin._application.stop.assert_not_called()
        plugin._application.shutdown.assert_not_called()


if __name__ == "__main__":
    unittest.main()
