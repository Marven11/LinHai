"""EndThinkPlugin单元测试。"""

import unittest
from unittest.mock import Mock, AsyncMock

from linhai.plugin import EndThinkPlugin
from linhai.base import Answer


class TestEndThinkPlugin(unittest.IsolatedAsyncioTestCase):
    """EndThinkPlugin测试类。"""

    def setUp(self):
        """测试前准备。"""
        self.registry = Mock()
        self.plugin = EndThinkPlugin(self.registry)
        self.answer = Mock(spec=Answer)
        self.agent = Mock()

        self.registry.get_member_typechecked = Mock(
            side_effect=lambda name, t: self.agent
        )

        self.agent.registry = Mock()
        self.agent.registry.send = AsyncMock()

        self.agent.agent_llm = AsyncMock()

        self.agent.message_processor = Mock()
        self.agent.message_processor.get_messages.return_value = []

    async def test_detect_end_think_alone(self):
        """测试检测到单独一行的</think>。"""
        current_content = """这是一些内容
</think>
其他内容"""

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)

    async def test_detect_end_think_with_whitespace(self):
        """测试检测到带空格的</think>。"""
        current_content = """这是一些内容
   </think>   
其他内容"""

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)

    async def test_ignore_end_think_in_context(self):
        """测试忽略上下文中的</think>。"""
        current_content = """这是一些内容包含</think>标记
但不是单独一行"""

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.registry.send.assert_not_called()
        self.answer.interrupt.assert_not_called()
        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    async def test_no_end_think(self):
        """测试没有</think>的情况。"""
        current_content = """这是一些正常的内容
没有任何问题"""

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertFalse(result)
        self.agent.registry.send.assert_not_called()
        self.answer.interrupt.assert_not_called()
        self.assertEqual(len(self.agent.message_processor.get_messages()), 0)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = Mock()

        self.plugin.register(lifecycle)

        lifecycle.after_token_generation.register.assert_called_once_with(
            self.plugin.after_token_generation
        )


if __name__ == "__main__":
    unittest.main()
