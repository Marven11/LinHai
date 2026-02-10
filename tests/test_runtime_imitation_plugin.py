"""Unit tests for RuntimeImitationPlugin."""

import unittest
from unittest.mock import MagicMock, AsyncMock

from linhai.plugin import RuntimeImitationPlugin
from linhai.llm import OpenAi


class TestRuntimeImitationPlugin(unittest.IsolatedAsyncioTestCase):
    """测试RuntimeImitationPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.agent = MagicMock()
        self.agent.message_processor = MagicMock()
        self.agent.message_processor.get_messages = MagicMock(return_value=[])
        self.agent.message_processor.add_new_message = MagicMock()
        self.agent.interrupt = AsyncMock()
        self.agent.get_current_model = MagicMock()

        self.group_chat = MagicMock()
        self.group_chat.get_member_typechecked = MagicMock(return_value=self.agent)
        self.group_chat.send_if_exists = AsyncMock()

        self.plugin = RuntimeImitationPlugin(self.group_chat)
        self.answer = MagicMock()

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_token_generation.assert_called_once_with(
            self.plugin.after_token_generation
        )

    async def test_after_token_generation_deepseek_tool_tag_first_line(self):
        """测试deepseek模型在第一行输出<<tool>>时被拦截。"""
        # 模拟deepseek模型
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<<tool>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        # 应该被拦截
        self.assertTrue(result)
        self.agent.interrupt.assert_called_once()
        interrupt_msg = self.agent.interrupt.call_args[0][0]
        self.assertIn("不要模仿tool的输出", interrupt_msg)

    async def test_after_token_generation_deepseek_tool_tag_not_first_line(self):
        """测试deepseek模型在非第一行输出<<tool>>时也应该被拦截（这是当前漏洞）。"""
        # 模拟deepseek模型
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        # <<tool>>出现在第二行，前面有换行符
        current_content = "\n<<tool>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        # 这个测试应该失败，因为当前实现只匹配行首
        # 但为了检测漏洞，我们期望它应该被拦截
        # 所以这里我们断言应该为True，但实际会返回False
        self.assertTrue(result, "漏洞：非第一行的<<tool>>标签没有被拦截")
        self.agent.interrupt.assert_called_once()

    async def test_after_token_generation_deepseek_tool_tag_with_spaces(self):
        """测试deepseek模型输出前面有空格的<<tool>>时也应该被拦截（这也是漏洞）。"""
        # 模拟deepseek模型
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        # <<tool>>前面有空格
        current_content = "    <<tool>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        # 这个测试应该失败，因为当前实现只匹配行首
        self.assertTrue(result, "漏洞：前面有空格的<<tool>>标签没有被拦截")
        self.agent.interrupt.assert_called_once()

    async def test_after_token_generation_deepseek_agent_tag_first_line(self):
        """测试deepseek模型在第一行输出<<agent>>时被拦截。"""
        # 模拟deepseek模型
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<<agent>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.interrupt.assert_called_once()
        interrupt_msg = self.agent.interrupt.call_args[0][0]
        self.assertIn("不要输出<<agent>>这个tag", interrupt_msg)

    async def test_after_token_generation_non_deepseek_model(self):
        """测试非deepseek模型时不被拦截。"""
        # 模拟非deepseek模型
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "qwen"
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<<tool>>"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        # main branch修改后，现在对所有模型都会检查<<tool>>标签
        self.assertTrue(result)
        self.agent.interrupt.assert_called_once()

    async def test_after_token_generation_tool_xml_start(self):
        """测试以<tool>{开头的XML格式工具调用被拦截。"""
        # 模拟deepseek模型
        mock_model = MagicMock(spec=OpenAi)
        mock_model.compatibility = "deepseek"
        self.agent.get_current_model = MagicMock(return_value=mock_model)

        current_content = "<tool>{"

        result = await self.plugin.after_token_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)
        self.agent.interrupt.assert_called_once()
        interrupt_msg = self.agent.interrupt.call_args[0][0]
        self.assertIn("工具调用的格式是```json toolcall不是XML", interrupt_msg)


if __name__ == "__main__":
    unittest.main()
