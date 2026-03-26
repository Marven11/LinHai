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
        self.assertIsNone(plugin._bot)
        self.assertIsNone(plugin._application)
        self.assertFalse(plugin._running)
        self.assertIsNotNone(plugin.send_queue)
        self.assertIsNone(plugin._send_task)
        self.assertEqual(plugin._send_delay, 5.0)

    async def test_after_segment_finished_normal(self):
        """测试处理normal segment，将消息加入队列。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        segment = {"segment_type": "normal", "content": "test content"}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.send_queue), 1)
        self.assertEqual(plugin.send_queue[0], "test content")

    async def test_after_segment_finished_reasoning(self):
        """测试不处理reasoning segment。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        segment = {"segment_type": "reasoning", "content": "test content"}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.send_queue), 0)

    async def test_after_segment_finished_empty_content(self):
        """测试不处理空内容的segment。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        segment = {"segment_type": "normal", "content": "   "}
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.send_queue), 0)

    async def test_after_segment_finished_duplicate(self):
        """测试相同内容会被加入队列两次。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)

        segment = {"segment_type": "normal", "content": "test content"}
        await plugin.after_segment_finished(None, segment)
        await plugin.after_segment_finished(None, segment)

        self.assertEqual(len(plugin.send_queue), 2)
        self.assertEqual(plugin.send_queue[0], "test content")
        self.assertEqual(plugin.send_queue[1], "test content")

    async def test_send_loop_with_no_bot(self):
        """测试bot为None时，消息被放回队头并增加延迟。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._running = True
        plugin.send_queue.append("test message")

        async def run_one_iteration():
            if plugin.send_queue:
                content = plugin.send_queue.popleft()
                if plugin._bot is None:
                    plugin.send_queue.appendleft(content)
                    await asyncio.sleep(plugin._send_delay)
                    plugin._send_delay *= 1.5
                    return

        await run_one_iteration()

        self.assertEqual(len(plugin.send_queue), 1)
        self.assertEqual(plugin.send_queue[0], "test message")
        self.assertGreater(plugin._send_delay, 5.0)

    async def test_send_loop_with_bot(self):
        """测试bot存在时成功发送消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._running = True
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock()
        plugin.send_queue.append("test message")

        async def run_one_iteration():
            if plugin.send_queue:
                content = plugin.send_queue.popleft()
                if plugin._bot is not None:
                    result = await asyncio.gather(
                        plugin._bot.send_message(
                            chat_id=plugin.config.default_chat_id,
                            text=content,
                        ),
                        return_exceptions=True,
                    )
                    if result[0] is None:
                        plugin._send_delay = 5.0

        await run_one_iteration()

        self.assertEqual(len(plugin.send_queue), 0)
        self.assertEqual(plugin._send_delay, 5.0)
        plugin._bot.send_message.assert_called_once()

    async def test_send_loop_with_error(self):
        """测试发送失败时消息被放回队头并增加延迟。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._running = True
        plugin._bot = Mock()
        plugin._bot.send_message = AsyncMock(side_effect=Exception("Network error"))
        plugin.send_queue.append("test message")

        async def run_one_iteration():
            if plugin.send_queue:
                content = plugin.send_queue.popleft()
                if plugin._bot is not None:
                    result = await asyncio.gather(
                        plugin._bot.send_message(
                            chat_id=plugin.config.default_chat_id,
                            text=content,
                        ),
                        return_exceptions=True,
                    )
                    if result[0] is not None:
                        plugin.send_queue.appendleft(content)
                        await asyncio.sleep(plugin._send_delay)
                        plugin._send_delay *= 1.5

        await run_one_iteration()

        self.assertEqual(len(plugin.send_queue), 1)
        self.assertEqual(plugin.send_queue[0], "test message")
        self.assertGreater(plugin._send_delay, 5.0)

    async def test_send_loop_exponential_backoff(self):
        """测试指数回避机制。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._running = True
        initial_delay = plugin._send_delay

        for i in range(3):
            plugin._send_delay *= 1.5

        expected_delay = initial_delay * (1.5**3)
        self.assertAlmostEqual(plugin._send_delay, expected_delay)

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

    async def test_handle_telegram_message_state_switch(self):
        """测试telegram消息加入后agent状态从waiting_user切换到working。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        self.agent.state = "waiting_user"
        self.agent.generate_response = AsyncMock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"
        mock_update.message.message_id = 123

        await plugin._handle_telegram_message(mock_update, None)

        self.assertEqual(self.agent.state, "working")
        self.agent.generate_response.assert_called_once()

    async def test_handle_telegram_message_state_already_working(self):
        """测试agent已经在working状态时不会重复调用generate_response。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        self.agent.state = "working"
        self.agent.generate_response = AsyncMock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.text = "Hello"
        mock_update.message.message_id = 123

        await plugin._handle_telegram_message(mock_update, None)

        self.assertEqual(self.agent.state, "working")
        self.agent.generate_response.assert_not_called()

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

    async def test_handle_telegram_sticker_valid(self):
        """测试处理有效的sticker消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
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
            await plugin._handle_telegram_sticker(mock_update, None)

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0][0]
        self.assertEqual(call_args, mock_sticker_message)

    async def test_handle_telegram_sticker_state_switch(self):
        """测试sticker消息加入后agent状态从waiting_user切换到working。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        mock_file = Mock()
        mock_file.download_as_bytearray = AsyncMock(
            return_value=bytearray(b"fake_sticker_data")
        )
        plugin._bot.get_file = AsyncMock(return_value=mock_file)
        self.agent.state = "waiting_user"

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        with patch("linhai.plugin.telegram.load_sticker") as mock_load_sticker:
            mock_sticker_message = Mock()
            mock_load_sticker.return_value = mock_sticker_message
            await plugin._handle_telegram_sticker(mock_update, None)

        self.assertEqual(self.agent.state, "working")

    async def test_handle_telegram_sticker_invalid_chat_id(self):
        """测试处理来自未授权chat_id的sticker消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "invalid_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        await plugin._handle_telegram_sticker(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()
        plugin._bot.get_file.assert_not_called()

    async def test_handle_telegram_sticker_no_sticker(self):
        """测试处理没有sticker字段的消息。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = None

        await plugin._handle_telegram_sticker(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()
        plugin._bot.get_file.assert_not_called()

    async def test_handle_telegram_sticker_no_bot(self):
        """测试bot为None时不处理sticker。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = None

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        await plugin._handle_telegram_sticker(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_handle_telegram_sticker_exception(self):
        """测试下载sticker失败时的异常处理。"""
        plugin = TelegramPlugin(self.group_chat, self.telegram_config)
        plugin._bot = Mock()
        plugin._bot.get_file = AsyncMock(side_effect=Exception("Download failed"))

        mock_update = Mock()
        mock_update.message = Mock()
        mock_update.message.chat_id = "test_chat_id"
        mock_update.message.sticker = Mock()
        mock_update.message.sticker.file_id = "test_file_id"

        await plugin._handle_telegram_sticker(mock_update, None)

        self.agent.message_processor.add_new_message.assert_not_called()

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
