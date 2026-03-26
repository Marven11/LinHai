"""Tests for MultimodalToolsetManager."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

from linhai.multimodal import MultimodalToolsetManager, load_image
from linhai.tool.base import ToolSet
from linhai.agent.base import RuntimeMessage


class TestMultimodalToolsetManager(unittest.IsolatedAsyncioTestCase):
    """Test MultimodalToolsetManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()
        self.mock_tool_manager = MagicMock()
        self.mock_tool_manager._toolsets = []

        self.mock_agent = AsyncMock()
        self.mock_llm = MagicMock()
        self.mock_llm.get_name.return_value = "kimi"
        self.mock_llm.support_image.return_value = True
        self.mock_agent.llm = self.mock_llm
        # Make get_current_model return the mock_llm directly (sync)
        self.mock_agent.get_current_model = MagicMock(return_value=self.mock_llm)
        self.mock_agent.message_processor = AsyncMock()

        self.mock_config = MagicMock()
        # 创建LLM配置mock，使用spec来避免MagicMock的name参数问题
        kimi_config = MagicMock()
        kimi_config.name = "kimi"
        kimi_config.support_image = True

        deepseek_config = MagicMock()
        deepseek_config.name = "deepseek"
        deepseek_config.support_image = False

        self.mock_config.llm = [kimi_config, deepseek_config]
        self.mock_agent.config = self.mock_config

        def mock_get_member_typechecked(name, cls=None):
            if name == "tool_manager":
                return self.mock_tool_manager
            elif name == "agent":
                return self.mock_agent
            return MagicMock()

        self.mock_group_chat.get_member_typechecked = mock_get_member_typechecked
        self.mock_group_chat.register_member = MagicMock()

    def test_init_creates_toolset(self):
        """Test that __init__ creates a ToolSet."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        self.assertIsInstance(manager.toolset, ToolSet)
        self.mock_group_chat.register_member.assert_called_once_with(
            "multimodal_toolset_manager", manager
        )

    def test_toolset_is_public_attribute(self):
        """Test that toolset is a public attribute."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        self.assertTrue(hasattr(manager, "toolset"))
        self.assertIsInstance(manager.toolset, ToolSet)

    async def test_adds_load_image_when_llm_supports_image(self):
        """Test that load_image is added when LLM supports image."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        # Initially no tool
        self.assertFalse(manager.toolset.has_tool("load_image"))

        # Mock lifecycle callback
        await manager._update_tool_availability()

        # Now should have the tool
        self.assertTrue(manager.toolset.has_tool("load_image"))

    async def test_removes_load_image_when_llm_does_not_support_image(self):
        """Test that load_image is removed when LLM does not support image."""
        # Set up with non-image-supporting LLM
        self.mock_llm.get_name.return_value = "deepseek"
        self.mock_llm.support_image.return_value = False

        manager = MultimodalToolsetManager(self.mock_group_chat)

        # Manually add the tool first
        manager.toolset.register_tool(
            name="load_image",
            desc="加载图片文件并返回图片数据，用于多模态LLM查看图片内容",
            args={
                "image_filepath": MagicMock(
                    desc="图片文件在master_host的路径", type="str"
                ),
            },
            required_args=["image_filepath"],
        )(load_image)

        self.assertTrue(manager.toolset.has_tool("load_image"))

        # Mock lifecycle callback
        await manager._update_tool_availability()

        # Now should not have the tool
        self.assertFalse(manager.toolset.has_tool("load_image"))

    async def test_adds_runtime_message_when_switching_to_image_supporting_llm(self):
        """Test that RuntimeMessage is added when switching to image-supporting LLM."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        # First call: LLM does not support image
        self.mock_llm.support_image.return_value = False
        await manager._update_tool_availability()

        # Should not add message because no tool is added or removed
        self.mock_agent.message_processor.add_new_message.assert_not_called()

        # Second call: LLM supports image (switch)
        self.mock_llm.support_image.return_value = True
        await manager._update_tool_availability()

        # Should add message about adding tool
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args
        self.assertIsInstance(call_args[0][0], RuntimeMessage)
        self.assertEqual(
            call_args[0][0].message, "当前LLM支持多模态，已添加load_image工具"
        )

    async def test_adds_runtime_message_when_switching_to_non_image_supporting_llm(
        self,
    ):
        """Test that RuntimeMessage is added when switching to non-image-supporting LLM."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        # First call: LLM supports image
        self.mock_llm.support_image.return_value = True
        await manager._update_tool_availability()

        # Should add message because tool is added
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args
        self.assertIsInstance(call_args[0][0], RuntimeMessage)
        self.assertEqual(
            call_args[0][0].message, "当前LLM支持多模态，已添加load_image工具"
        )

        # Reset mock for second call
        self.mock_agent.message_processor.add_new_message.reset_mock()

        # Second call: LLM does not support image (switch)
        self.mock_llm.support_image.return_value = False
        await manager._update_tool_availability()

        # Should add message about removing tool
        self.mock_agent.message_processor.add_new_message.assert_called_once()
        call_args = self.mock_agent.message_processor.add_new_message.call_args
        self.assertIsInstance(call_args[0][0], RuntimeMessage)
        self.assertEqual(
            call_args[0][0].message, "当前LLM不支持多模态，已移除load_image工具"
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
