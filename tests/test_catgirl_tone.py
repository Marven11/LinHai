"""测试CatgirlTonePlugin类。"""

import unittest
import time
from unittest.mock import MagicMock, AsyncMock

from linhai.plugin.catgirl_tone import CatgirlTonePlugin
from linhai.agent.messages import RuntimeMessage


class TestCatgirlTonePlugin(unittest.IsolatedAsyncioTestCase):
    """测试CatgirlTonePlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = AsyncMock()
        self.registry = MagicMock()
        self.registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, t: self.agent
        )
        self.plugin = CatgirlTonePlugin(self.registry)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.after_segment_finished.register.assert_called_once_with(
            self.plugin.after_segment_finished
        )

    async def test_after_segment_finished_normal_line_with_awkward_ending(self):
        """测试检测到生硬猫娘语气结尾时发送警告。"""
        segment = {"segment_type": "normal", "content": "我需要修改这个文件。喵~"}

        self.plugin._last_warning_time = None  # 确保可以发送警告

        await self.plugin.after_segment_finished(None, segment)

        self.agent.message_processor.add_new_message.assert_called_once()
        call_args = self.agent.message_processor.add_new_message.call_args[0]
        self.assertIsInstance(call_args[0], RuntimeMessage)
        self.assertIn("你生硬地输出了喵", call_args[0].message)
        self.assertIsNotNone(self.plugin._last_warning_time)

    async def test_after_segment_finished_normal_line_without_awkward_ending(self):
        """测试没有生硬猫娘语气结尾时不发送警告。"""
        segment = {"segment_type": "normal", "content": "我需要修改这个文件。"}

        await self.plugin.after_segment_finished(None, segment)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_segment_finished_multiple_lines(self):
        """测试多行内容时不处理。"""
        segment = {"segment_type": "normal", "content": "第一行\n第二行。喵~"}

        await self.plugin.after_segment_finished(None, segment)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_segment_finished_non_normal_segment(self):
        """测试非normal类型的segment时不处理。"""
        segment = {"segment_type": "reasoning", "content": "我需要思考一下。喵~"}

        await self.plugin.after_segment_finished(None, segment)

        self.agent.message_processor.add_new_message.assert_not_called()

    async def test_after_segment_finished_warning_cooldown(self):
        """测试警告冷却时间机制。"""
        segment = {"segment_type": "normal", "content": "我需要修改这个文件。喵~"}

        # 第一次警告
        await self.plugin.after_segment_finished(None, segment)
        first_call_count = self.agent.message_processor.add_new_message.call_count

        # 立即第二次调用，应该被冷却时间阻止
        self.agent.message_processor.add_new_message.reset_mock()
        await self.plugin.after_segment_finished(None, segment)

        self.agent.message_processor.add_new_message.assert_not_called()

        # 模拟冷却时间过后
        self.plugin._last_warning_time = time.time() - 130  # 超过120秒
        await self.plugin.after_segment_finished(None, segment)

        self.agent.message_processor.add_new_message.assert_called_once()

    async def test_various_awkward_endings(self):
        """测试各种生硬的猫娘语气结尾。"""
        test_cases = [
            ("我需要修改这个文件。喵~", True),
            ("我需要修改这个文件。喵。", True),
            ("我需要修改这个文件。喵！", True),
            ("正常句子。", False),
            ("多行内容\n第二行", False),
        ]

        for content, should_warn in test_cases:
            self.agent.message_processor.add_new_message.reset_mock()
            self.plugin._last_warning_time = None  # 重置警告时间

            segment = {"segment_type": "normal", "content": content}

            await self.plugin.after_segment_finished(None, segment)

            if should_warn:
                self.agent.message_processor.add_new_message.assert_called_once()
            else:
                self.agent.message_processor.add_new_message.assert_not_called()
