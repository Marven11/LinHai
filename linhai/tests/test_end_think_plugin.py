"""EndThinkPlugin单元测试。"""

import unittest
from unittest.mock import Mock, AsyncMock

from linhai.agent.agent_plugin import EndThinkPlugin
from linhai.llm import Answer


class TestEndThinkPlugin(unittest.TestCase):
    """EndThinkPlugin测试类。"""

    def setUp(self):
        """测试前准备。"""
        self.group_chat = Mock()
        self.plugin = EndThinkPlugin(self.group_chat)
        self.answer = Mock(spec=Answer)
        self.agent = Mock()
        
        # 模拟group_chat.get_members返回agent
        self.group_chat.get_members.return_value = self.agent
        
        # 模拟agent的group_chat.send方法
        self.agent.group_chat = Mock()
        self.agent.group_chat.send = AsyncMock()
        
        # 模拟agent的messages列表
        self.agent.messages = []

    async def test_detect_end_think_alone(self):
        """测试检测到单独一行的</think>。"""
        # 设置包含单独</think>的内容
        current_content = """这是一些内容
</think>
其他内容"""
        
        # 调用插件方法
        result = await self.plugin.during_message_generation(self.answer, current_content)
        
        # 验证结果
        self.assertTrue(result)
        self.agent.group_chat.send.assert_called_once_with("cli_agent_output", self.answer)
        self.answer.interrupt.assert_called_once()
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("检测到只有'</think>'的行", self.agent.messages[0].content)

    async def test_detect_end_think_with_whitespace(self):
        """测试检测到带空格的</think>。"""
        # 设置包含带空格的</think>的内容
        current_content = """这是一些内容
   </think>   
其他内容"""
        
        # 调用插件方法
        result = await self.plugin.during_message_generation(self.answer, current_content)
        
        # 验证结果
        self.assertTrue(result)
        self.agent.group_chat.send.assert_called_once_with("cli_agent_output", self.answer)
        self.answer.interrupt.assert_called_once()

    async def test_ignore_end_think_in_context(self):
        """测试忽略上下文中的</think>。"""
        # 设置包含在上下文中的</think>的内容
        current_content = """这是一些内容包含</think>标记
但不是单独一行"""
        
        # 调用插件方法
        result = await self.plugin.during_message_generation(self.answer, current_content)
        
        # 验证结果
        self.assertFalse(result)
        self.agent.group_chat.send.assert_not_called()
        self.answer.interrupt.assert_not_called()
        self.assertEqual(len(self.agent.messages), 0)

    async def test_no_end_think(self):
        """测试没有</think>的情况。"""
        # 设置不包含</think>的内容
        current_content = """这是一些正常的内容
没有任何问题"""
        
        # 调用插件方法
        result = await self.plugin.during_message_generation(self.answer, current_content)
        
        # 验证结果
        self.assertFalse(result)
        self.agent.group_chat.send.assert_not_called()
        self.answer.interrupt.assert_not_called()
        self.assertEqual(len(self.agent.messages), 0)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = Mock()
        
        # 调用注册方法
        self.plugin.register(lifecycle)
        
        # 验证注册了正确的回调
        lifecycle.register_during_message_generation.assert_called_once_with(
            self.plugin.during_message_generation
        )


if __name__ == "__main__":
    unittest.main()