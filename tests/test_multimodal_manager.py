"""Tests for MultimodalToolsetManager."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from linhai.multimodal import MultimodalToolsetManager, load_image
from linhai.tool.base import ToolSet


class TestMultimodalToolsetManager(TestCase):
    """Test MultimodalToolsetManager class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_group_chat = MagicMock()
        self.mock_tool_manager = MagicMock()
        self.mock_tool_manager._toolsets = []

        self.mock_agent = MagicMock()
        self.mock_llm = MagicMock()
        self.mock_llm.get_name.return_value = "kimi"
        self.mock_llm.support_image.return_value = True
        self.mock_agent.llm = self.mock_llm
        # Make get_current_model return the mock_llm directly (sync)
        self.mock_agent.get_current_model = MagicMock(return_value=self.mock_llm)

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

        def mock_get_members(name, cls=None):
            if name == "tool_manager":
                return self.mock_tool_manager
            elif name == "agent":
                return self.mock_agent
            return MagicMock()

        self.mock_group_chat.get_members = mock_get_members
        self.mock_group_chat.register_member = MagicMock()

    def test_init_creates_toolset(self):
        """Test that __init__ creates a ToolSet."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        self.assertIsInstance(manager._toolset, ToolSet)
        self.mock_group_chat.register_member.assert_called_once_with(
            "multimodal_toolset_manager", manager
        )

    def test_init_adds_toolset_to_manager(self):
        """Test that __init__ adds the ToolSet to ToolManager."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        self.mock_tool_manager.add_toolset.assert_called_once_with(manager._toolset)

    def test_adds_load_image_when_llm_supports_image(self):
        """Test that load_image is added when LLM supports image."""
        manager = MultimodalToolsetManager(self.mock_group_chat)

        # Initially no tool
        self.assertFalse(manager._toolset.has_tool("load_image"))

        # Mock lifecycle callback
        import asyncio

        asyncio.run(manager._update_tool_availability(False, False))

        # Now should have the tool
        self.assertTrue(manager._toolset.has_tool("load_image"))

    def test_removes_load_image_when_llm_does_not_support_image(self):
        """Test that load_image is removed when LLM does not support image."""
        # Set up with non-image-supporting LLM
        self.mock_llm.get_name.return_value = "deepseek"
        self.mock_llm.support_image.return_value = False

        manager = MultimodalToolsetManager(self.mock_group_chat)

        # Manually add the tool first
        manager._toolset.register_tool(
            name="load_image",
            desc="加载图片文件并返回图片数据，用于多模态LLM查看图片内容",
            args={
                "image_path": MagicMock(desc="图片文件的绝对路径", type="str"),
            },
            required_args=["image_path"],
        )(load_image)

        self.assertTrue(manager._toolset.has_tool("load_image"))

        # Mock lifecycle callback
        import asyncio

        asyncio.run(manager._update_tool_availability(False, False))

        # Now should not have the tool
        self.assertFalse(manager._toolset.has_tool("load_image"))


if __name__ == "__main__":
    import unittest

    unittest.main()
