import unittest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from linhai.plugin.telegram import TelegramPlugin, TelegramReactionReminderPlugin
from linhai.agent.create import TelegramContext
from linhai.agent.state_machine import AgentStateMachine
from linhai.telegram import TelegramMessage
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


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

    def test_on_segment_start_normal(self):
        """测试处理normal segment，将消息加入队列。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {
            "segment_type": "normal",
            "content": "test content",
            "is_finished": False,
        }
        asyncio.run(plugin._on_segment_start(None, segment))

        self.assertEqual(len(plugin.send_queue), 1)
        self.assertIs(plugin.send_queue[0], segment)

    def test_on_segment_start_reasoning(self):
        """测试不处理reasoning segment。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {
            "segment_type": "reasoning",
            "content": "test content",
            "is_finished": False,
        }
        asyncio.run(plugin._on_segment_start(None, segment))

        self.assertEqual(len(plugin.send_queue), 0)

    def test_on_segment_start_empty_content(self):
        """测试空内容的segment仍会加入队列（内容后续会增长）。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment = {"segment_type": "normal", "content": "   ", "is_finished": False}
        asyncio.run(plugin._on_segment_start(None, segment))

        self.assertEqual(len(plugin.send_queue), 1)

    def test_on_segment_start_duplicate(self):
        """测试相同内容会被加入队列两次（每个segment独立）。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        segment1 = {
            "segment_type": "normal",
            "content": "test content",
            "is_finished": False,
        }
        segment2 = {
            "segment_type": "normal",
            "content": "test content",
            "is_finished": False,
        }
        asyncio.run(plugin._on_segment_start(None, segment1))
        asyncio.run(plugin._on_segment_start(None, segment2))

        self.assertEqual(len(plugin.send_queue), 2)
        self.assertIs(plugin.send_queue[0], segment1)
        self.assertIs(plugin.send_queue[1], segment2)

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
        """测试Agent循环开始时启动telegram bot，使用run_polling + task supervisor。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        with (
            patch("linhai.plugin.telegram.Application") as mock_app_class,
            patch("telegram.Bot") as mock_bot_class,
        ):
            mock_bot = Mock()
            mock_bot_class.return_value = mock_bot
            mock_builder = Mock()
            mock_application = Mock()
            mock_application.run_polling = AsyncMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.bot.return_value = mock_builder
            mock_builder.build.return_value = mock_application
            mock_app_class.builder.return_value = mock_builder

            asyncio.run(plugin.before_agent_loop(None))

            self.assertTrue(plugin._running)
            self.assertIs(plugin._bot, mock_bot)
            mock_bot_class.assert_called_once_with(token="test_token")

    def test_before_agent_loop_creates_supervised_tasks(self):
        """测试before_agent_loop创建telegram_polling和telegram_send_loop任务。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)

        task_supervisor_mock = Mock()
        task_supervisor_mock.create_supervised_task = Mock()
        self.registry.get_member_typechecked = Mock(
            side_effect=lambda name, cls: (
                task_supervisor_mock if name == "task_supervisor" else self.agent
            )
        )

        with (
            patch("linhai.plugin.telegram.Application") as mock_app_class,
            patch("telegram.Bot") as mock_bot_class,
        ):
            mock_bot = Mock()
            mock_bot_class.return_value = mock_bot
            mock_builder = Mock()
            mock_application = Mock()
            mock_application.run_polling = Mock()
            mock_builder.token.return_value = mock_builder
            mock_builder.bot.return_value = mock_builder
            mock_builder.build.return_value = mock_application
            mock_app_class.builder.return_value = mock_builder

            asyncio.run(plugin.before_agent_loop(None))

            create_calls = task_supervisor_mock.create_supervised_task.call_args_list
            self.assertEqual(len(create_calls), 2)
            self.assertEqual(create_calls[0][0][0], "telegram_polling")
            self.assertIs(
                create_calls[0][0][1].__func__, plugin._run_polling_forever.__func__
            )
            self.assertEqual(create_calls[1][0][0], "telegram_send_loop")

    def test_run_polling_forever_calls_async_api(self):
        """测试_run_polling_forever调用initialize、start和updater.start_polling。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._application = Mock()
        plugin._application.initialize = AsyncMock()
        plugin._application.start = AsyncMock()
        plugin._application.updater = Mock()
        plugin._application.updater.start_polling = AsyncMock()
        plugin._running = True

        async def run_and_stop():
            task = asyncio.create_task(plugin._run_polling_forever())
            await asyncio.sleep(0.1)
            plugin._running = False
            await asyncio.sleep(0.1)
            await task

        asyncio.run(run_and_stop())

        plugin._application.initialize.assert_called_once()
        plugin._application.start.assert_called_once()
        plugin._application.updater.start_polling.assert_called_once_with(
            bootstrap_retries=-1
        )

    def test_run_polling_forever_stops_when_not_running(self):
        """测试_run_polling_forever在_running为False时不启动polling。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin._application = Mock()
        plugin._application.initialize = AsyncMock()
        plugin._application.start = AsyncMock()
        plugin._application.updater = Mock()
        plugin._application.updater.start_polling = AsyncMock()
        plugin._running = False

        asyncio.run(plugin._run_polling_forever())

        plugin._application.initialize.assert_not_called()
        plugin._application.updater.start_polling.assert_not_called()

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
        """测试关闭telegram bot，取消任务并停止Application。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        task_supervisor_mock = Mock()
        task_supervisor_mock.cancel = Mock()
        self.registry.get_member_typechecked = Mock(return_value=task_supervisor_mock)
        plugin._application = Mock()
        plugin._application.stop = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._running = True

        asyncio.run(plugin.shutdown())

        self.assertFalse(plugin._running)
        cancel_calls = task_supervisor_mock.cancel.call_args_list
        self.assertEqual(len(cancel_calls), 2)
        self.assertEqual(cancel_calls[0][0][0], "telegram_send_loop")
        self.assertEqual(cancel_calls[1][0][0], "telegram_polling")
        plugin._application.stop.assert_called_once()
        plugin._application.shutdown.assert_called_once()

    def test_shutdown_not_running(self):
        """测试bot未运行时不执行关闭。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        task_supervisor_mock = Mock()
        task_supervisor_mock.cancel = Mock()
        self.registry.get_member_typechecked = Mock(return_value=task_supervisor_mock)
        plugin._application = Mock()
        plugin._application.stop = AsyncMock()
        plugin._application.shutdown = AsyncMock()
        plugin._running = False

        asyncio.run(plugin.shutdown())

        task_supervisor_mock.cancel.assert_not_called()
        plugin._application.stop.assert_not_called()
        plugin._application.shutdown.assert_not_called()

    def test_on_exit_calls_shutdown(self):
        """测试_on_exit调用shutdown。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        plugin.shutdown = AsyncMock()
        asyncio.run(plugin._on_exit())
        plugin.shutdown.assert_called_once()

    def test_register_includes_before_exit(self):
        """测试register注册before_exit回调。"""
        plugin = TelegramPlugin(self.registry, self.telegram_config)
        lifecycle_mock = Mock()
        lifecycle_mock.after_segment = Mock()
        lifecycle_mock.after_segment.register = Mock()
        lifecycle_mock.before_agent_loop = Mock()
        lifecycle_mock.before_agent_loop.register = Mock()
        lifecycle_mock.before_exit = Mock()
        lifecycle_mock.before_exit.register = Mock()

        plugin.register(lifecycle_mock)

        lifecycle_mock.before_exit.register.assert_called_once()
        call_arg = lifecycle_mock.before_exit.register.call_args[0][0]
        self.assertEqual(call_arg.__func__, plugin._on_exit.__func__)
        self.assertIs(call_arg.__self__, plugin)


class TestTelegramReactionReminderPlugin(unittest.TestCase):
    """TelegramReactionReminderPlugin单元测试。"""

    def setUp(self):
        self.registry = Mock()
        self.agent = Mock()
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

        def get_member(name, cls):
            return self.agent

        self.registry.get_member_typechecked = Mock(side_effect=get_member)

    def test_reminder_added_when_not_responded(self):
        """has_responded为False时添加提醒通知。"""
        plugin = TelegramReactionReminderPlugin(self.registry)

        asyncio.run(plugin._before_message_generation())

        self.agent.message_processor.update_notification_message.assert_called_once()
        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertEqual(call_args[1]["source"], "telegram_reaction_reminder")
        self.assertIsNotNone(call_args[0][0])

    def test_reminder_cleared_when_has_responded(self):
        """has_responded为True时清空通知并重置。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        plugin._has_responded = True

        asyncio.run(plugin._before_message_generation())

        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIsNone(call_args[0][0])

    def test_before_message_generation_keeps_has_responded(self):
        """before_message_generation不重置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        plugin._has_responded = True

        asyncio.run(plugin._before_message_generation())

        self.assertTrue(plugin._has_responded)

    def test_segment_finished_sets_responded(self):
        """非空normal segment结束时设置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        segment = {"segment_type": "normal", "content": "hello", "is_finished": True}

        asyncio.run(plugin._on_segment_finished(None, segment))

        self.assertTrue(plugin._has_responded)

    def test_segment_finished_empty_not_set(self):
        """空normal segment不设置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        segment = {"segment_type": "normal", "content": "   ", "is_finished": True}

        asyncio.run(plugin._on_segment_finished(None, segment))

        self.assertFalse(plugin._has_responded)

    def test_segment_finished_reasoning_not_set(self):
        """reasoning segment不设置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        segment = {
            "segment_type": "reasoning",
            "content": "thinking",
            "is_finished": True,
        }

        asyncio.run(plugin._on_segment_finished(None, segment))

        self.assertFalse(plugin._has_responded)

    def test_reaction_tool_sets_responded(self):
        """send_telegram_reaction工具调用设置has_responded，不更新通知。"""
        plugin = TelegramReactionReminderPlugin(self.registry)

        asyncio.run(
            plugin._on_reaction_tool_called(
                tool_name="send_telegram_reaction",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        self.assertTrue(plugin._has_responded)
        self.agent.message_processor.update_notification_message.assert_not_called()

    def test_reaction_tool_failed_also_sets_responded(self):
        """send_telegram_reaction失败也设置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)

        asyncio.run(
            plugin._on_reaction_tool_called(
                tool_name="send_telegram_reaction",
                tool_index=0,
                status="failed",
                message=None,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        self.assertTrue(plugin._has_responded)

    def test_other_tool_does_not_set_responded(self):
        """其他工具调用不设置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)

        asyncio.run(
            plugin._on_reaction_tool_called(
                tool_name="web_search",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        self.assertFalse(plugin._has_responded)
        self.agent.message_processor.update_notification_message.assert_not_called()

    def test_full_cycle_segment_then_clear(self):
        """segment设置has_responded后，before_message_generation清空通知。"""
        plugin = TelegramReactionReminderPlugin(self.registry)

        segment = {"segment_type": "normal", "content": "hello", "is_finished": True}
        asyncio.run(plugin._on_segment_finished(None, segment))

        asyncio.run(plugin._before_message_generation())

        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIsNone(call_args[0][0])
        self.assertTrue(plugin._has_responded)

    def test_full_cycle_reaction_then_clear(self):
        """reaction设置has_responded后，before_message_generation清空通知。"""
        plugin = TelegramReactionReminderPlugin(self.registry)

        asyncio.run(
            plugin._on_reaction_tool_called(
                tool_name="send_telegram_reaction",
                tool_index=0,
                status="success",
                message=None,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )

        asyncio.run(plugin._before_message_generation())

        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIsNone(call_args[0][0])
        self.assertTrue(plugin._has_responded)

    def test_telegram_message_resets_has_responded(self):
        """TelegramMessage插入时重置has_responded为False。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        plugin._has_responded = True

        msg = TelegramMessage(chat_id="123", content="hello", message_id=1)
        asyncio.run(plugin._on_before_add_new_message(msg))

        self.assertFalse(plugin._has_responded)

    def test_non_telegram_message_does_not_reset(self):
        """非TelegramMessage不会重置has_responded。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        plugin._has_responded = True

        from linhai.agent.messages import RuntimeMessage

        msg = RuntimeMessage("some runtime message")
        asyncio.run(plugin._on_before_add_new_message(msg))

        self.assertTrue(plugin._has_responded)

    def test_telegram_message_then_reminder_shows(self):
        """TelegramMessage重置后，before_message_generation显示提醒。"""
        plugin = TelegramReactionReminderPlugin(self.registry)
        plugin._has_responded = True

        msg = TelegramMessage(chat_id="123", content="hello", message_id=1)
        asyncio.run(plugin._on_before_add_new_message(msg))
        asyncio.run(plugin._before_message_generation())

        call_args = self.agent.message_processor.update_notification_message.call_args
        self.assertIsNotNone(call_args[0][0])


class TestTelegramMessageGetContent(unittest.TestCase):
    """TelegramMessage.get_content测试。"""

    def test_get_content_includes_metadata(self):
        """测试get_content包含chat_id和message_id。"""
        msg = TelegramMessage(chat_id="123", content="hello", message_id=42)
        content = msg.get_content()
        self.assertIn("chat_id: 123", content)
        self.assertIn("message_id: 42", content)
        self.assertIn("hello", content)

    def test_get_content_format(self):
        """测试get_content格式正确。"""
        msg = TelegramMessage(chat_id="456", content="world", message_id=99)
        content = msg.get_content()
        self.assertTrue(content.startswith("<<telegram>>"))
        self.assertTrue(content.endswith("<<telegram>>"))


class TestTelegramPluginReactionToolset(unittest.TestCase):
    """TelegramPlugin reaction工具集测试。"""

    def test_create_toolset(self):
        """测试create_toolset返回有效ToolSet。"""
        registry = Mock()
        registry.send_if_exists = AsyncMock()
        telegram_config = TelegramContext(
            bot_token="test_token", default_chat_id="test_chat_id"
        )
        plugin = TelegramPlugin(registry, telegram_config)
        toolset = plugin.create_toolset()
        self.assertIsNotNone(toolset)

    def test_reaction_tool_no_bot(self):
        """测试bot未初始化时工具集包含正确工具。"""
        registry = Mock()
        registry.send_if_exists = AsyncMock()
        telegram_config = TelegramContext(
            bot_token="test_token", default_chat_id="test_chat_id"
        )
        plugin = TelegramPlugin(registry, telegram_config)
        toolset = plugin.create_toolset()
        tools = toolset.get_tools()
        self.assertIn("send_telegram_reaction", tools)

    def test_reaction_tool_no_message(self):
        """测试没有可回复消息时返回失败。"""
        registry = Mock()
        registry.send_if_exists = AsyncMock()
        telegram_config = TelegramContext(
            bot_token="test_token", default_chat_id="test_chat_id"
        )
        plugin = TelegramPlugin(registry, telegram_config)
        plugin._bot = Mock()
        toolset = plugin.create_toolset()
        result = asyncio.run(
            toolset.call_tool("send_telegram_reaction", {"emoji": "👀"})
        )
        self.assertIsInstance(result, FailedToolResult)

    def test_reaction_tool_success(self):
        """测试成功发送reaction。"""
        registry = Mock()
        registry.send_if_exists = AsyncMock()
        telegram_config = TelegramContext(
            bot_token="test_token", default_chat_id="test_chat_id"
        )
        plugin = TelegramPlugin(registry, telegram_config)
        plugin._bot = Mock()
        plugin._bot.set_message_reaction = AsyncMock(return_value=True)
        plugin._latest_chat_id = 123
        plugin._latest_message_id = 456
        toolset = plugin.create_toolset()
        result = asyncio.run(
            toolset.call_tool("send_telegram_reaction", {"emoji": "👀"})
        )
        self.assertIsInstance(result, SuccessfulToolResult)
        plugin._bot.set_message_reaction.assert_called_once()


if __name__ == "__main__":
    unittest.main()
