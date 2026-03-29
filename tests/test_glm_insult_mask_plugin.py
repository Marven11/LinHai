import unittest
import asyncio
from unittest.mock import Mock, MagicMock
from typing import cast

from linhai.plugin.message_checkers import GlmInsultMaskPlugin
from linhai.agent.base import RuntimeMessage
from linhai.llm import OpenAi


class MockRegistry:
    def __init__(self, agent=None):
        self.members = {}
        if agent:
            self.members["agent"] = agent

    def register_member(self, name, obj):
        self.members[name] = obj

    def get_member_typechecked(self, name, _type=None):
        if name in self.members:
            return self.members[name]
        raise RuntimeError(f"Member {name} not found")


class MockAgent:
    def __init__(self, compatibility):
        # 使用MagicMock(spec=OpenAi)来模拟模型，与OnlyReasoningPlugin测试一致
        self.model = MagicMock(spec=OpenAi)
        self.model.compatibility = compatibility
        # 设置必需的方法返回值
        self.model.get_token_limit.return_value = 4096
        self.model.get_name.return_value = "mock-glm"
        self.model.support_image.return_value = False
        self.model.get_explicit_cache_info.return_value = None

    def get_current_model(self):
        return self.model


class MockMessage:
    def __init__(self, content):
        self._content = content

    def get_content(self):
        return self._content


class TestGlmInsultMaskPlugin(unittest.TestCase):
    def setUp(self):
        pass

    def test_plugin_initialization(self):
        registry = MockRegistry()
        plugin = GlmInsultMaskPlugin(registry)
        self.assertEqual(
            plugin.INSULTS,
            {
                "傻逼": "shabi",
                "垃圾": "laji",
                "弱智": "ruozhi",
                "脑残": "naocan",
            },
        )

    def test_after_toolcall_non_glm_model(self):
        agent = MockAgent("deepseek")
        registry = MockRegistry(agent)
        plugin = GlmInsultMaskPlugin(registry)

        message = MockMessage("这是一个傻逼测试")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNone(result)

    def test_after_toolcall_glm_model_no_insult(self):
        agent = MockAgent("glm")
        registry = MockRegistry(agent)
        plugin = GlmInsultMaskPlugin(registry)

        message = MockMessage("这是一个正常测试")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsNone(result)

    def test_after_toolcall_glm_model_with_insult(self):
        agent = MockAgent("glm")
        registry = MockRegistry(agent)
        plugin = GlmInsultMaskPlugin(registry)

        message = MockMessage("这是一个傻逼测试")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsInstance(result, RuntimeMessage)
        expected_content = (
            "<<insult-mask>><<message>>你是GLM，当前工具结果中包含脏话，"
            "为了符合API TOS、保证正常运行，脏话已屏蔽为拼音<<message>><<masked>>"
            "这是一个shabi测试<<masked>><<insult-mask>>"
        )
        self.assertEqual(cast(RuntimeMessage, result).message, expected_content)

    def test_after_toolcall_glm_model_multiple_insults(self):
        agent = MockAgent("glm")
        registry = MockRegistry(agent)
        plugin = GlmInsultMaskPlugin(registry)

        message = MockMessage("傻逼和垃圾都是弱智")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsInstance(result, RuntimeMessage)
        expected_content = (
            "<<insult-mask>><<message>>你是GLM，当前工具结果中包含脏话，"
            "为了符合API TOS、保证正常运行，脏话已屏蔽为拼音<<message>><<masked>>"
            "shabi和laji都是ruozhi<<masked>><<insort-mask>>"
        )
        # 修复拼写错误
        expected_content_fixed = expected_content.replace(
            "<<insort-mask>>", "<<insult-mask>>"
        )
        self.assertEqual(cast(RuntimeMessage, result).message, expected_content_fixed)

    def test_after_toolcall_glm_model_partial_match(self):
        agent = MockAgent("glm")
        registry = MockRegistry(agent)
        plugin = GlmInsultMaskPlugin(registry)

        message = MockMessage("脑残粉不是脑残")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            plugin.after_toolcall(
                tool_name="test_tool",
                tool_index=0,
                status="success",
                message=message,
                toolcall_arguments={},
                with_secret=None,
                is_tool_failed_duplicated_error=False,
            )
        )
        loop.close()

        self.assertIsInstance(result, RuntimeMessage)
        expected_content = (
            "<<insult-mask>><<message>>你是GLM，当前工具结果中包含脏话，"
            "为了符合API TOS、保证正常运行，脏话已屏蔽为拼音<<message>><<masked>>"
            "naocan粉不是naocan<<masked>><<insult-mask>>"
        )
        self.assertEqual(cast(RuntimeMessage, result).message, expected_content)


if __name__ == "__main__":
    unittest.main()
