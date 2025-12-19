"""测试目录更改检测插件。"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from linhai.agent.plugin import DirectoryChangePlugin
from linhai.agent.base import PathMemory, GlobalMemory
from linhai.group_chat import GroupChat


class TestDirectoryChangePlugin(unittest.TestCase):
    """测试目录更改检测插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        self.plugin = DirectoryChangePlugin(self.group_chat)

        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()

        self.mock_agent = MagicMock()
        self.mock_agent.context = {"enable_directory_change_detection": False}

        from linhai.agent.message import AgentMessage
        from linhai.llm import UserMessage, AssistantMessage, SystemMessage
        from linhai.tool.main import ToolManager
        
        # 为SystemMessage初始化提供mock的tool_manager
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        
        def get_members_side_effect(member_type, _member_class=None):
            if member_type == "tool_manager":
                return mock_tool_manager
            elif member_type == "agent":
                return self.mock_agent
            else:
                return None
        
        self.group_chat.get_members = Mock(side_effect=get_members_side_effect)

        init_messages = [
            SystemMessage(
                group_chat=self.group_chat,
            ),
            UserMessage(message="Initial message"),
        ]
        self.mock_agent.message_processor = AgentMessage(self.group_chat, init_messages)

        self.get_members_patch = patch.object(
            self.group_chat, "get_members", return_value=self.mock_agent
        )
        self.mock_get_members = self.get_members_patch.start()

    def tearDown(self):
        """清理测试环境。"""
        os.chdir(self.original_cwd)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.get_members_patch.stop()

    def test_plugin_disabled_by_default(self):
        """测试插件默认禁用。"""
        self.mock_agent.context["enable_directory_change_detection"] = False

        initial_message_count = len(self.mock_agent.message_processor.get_messages())

        import asyncio

        asyncio.run(self.plugin.before_message_generation(True, False))

        final_message_count = len(self.mock_agent.message_processor.get_messages())
        self.assertEqual(final_message_count, initial_message_count)

    def test_plugin_enabled_no_directory_change(self):
        """测试插件启用但目录未更改。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        self.plugin.last_directory = Path.cwd()

        initial_message_count = len(self.mock_agent.message_processor.get_messages())

        import asyncio

        asyncio.run(self.plugin.before_message_generation(True, False))

        final_message_count = len(self.mock_agent.message_processor.get_messages())
        self.assertEqual(final_message_count, initial_message_count)

    def test_plugin_enabled_with_directory_change(self):
        """测试插件启用且目录更改。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        os.chdir(self.temp_dir)

        import asyncio

        asyncio.run(self.plugin.before_message_generation(True, False))

        self.assertIsNotNone(self.plugin.last_directory)
        if self.plugin.last_directory is not None:
            self.assertEqual(
                self.plugin.last_directory.resolve(), Path(self.temp_dir).resolve()
            )

    def test_plugin_detects_target_files(self):
        """测试插件检测目标文件。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        test_file = Path(self.temp_dir) / "LINHAI.md"
        test_file.write_text("# Test Memory\n\nTest content")

        os.chdir(self.temp_dir)

        import asyncio

        asyncio.run(self.plugin.before_message_generation(True, False))

        messages = self.mock_agent.message_processor.get_messages()
        pathmemory_count = sum(1 for msg in messages if isinstance(msg, PathMemory))
        self.assertEqual(pathmemory_count, 1)
        pathmemory_msg = next(msg for msg in messages if isinstance(msg, PathMemory))
        self.assertEqual(pathmemory_msg.filepath.resolve(), test_file.resolve())

    def test_plugin_avoids_duplicates(self):
        """测试插件避免重复添加相同路径的消息。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        test_file = Path(self.temp_dir) / "LINHAI.md"
        test_file.write_text("# Test Memory\n\nTest content")

        os.chdir(self.temp_dir)

        existing_memory = PathMemory(test_file)
        self.mock_agent.message_processor.add_new_message(existing_memory)

        import asyncio

        asyncio.run(self.plugin.before_message_generation(True, False))

        pathmemory_count = sum(
            1
            for msg in self.mock_agent.message_processor.get_messages()
            if isinstance(msg, PathMemory)
        )
        self.assertEqual(pathmemory_count, 1)

    def test_plugin_handles_global_memory_duplicates(self):
        """测试插件避免与GlobalMemory重复。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        test_file = Path(self.temp_dir) / "LINHAI.md"
        test_file.write_text("# Test Memory\n\nTest content")

        os.chdir(self.temp_dir)

        existing_memory = GlobalMemory(test_file)
        self.mock_agent.message_processor.add_new_message(existing_memory)

        import asyncio

        asyncio.run(self.plugin.before_message_generation(True, False))

        memory_count = sum(
            1
            for msg in self.mock_agent.message_processor.get_messages()
            if isinstance(msg, (PathMemory, GlobalMemory))
        )
        self.assertEqual(memory_count, 1)

    def test_plugin_registers_correctly(self):
        """测试插件正确注册到生命周期。"""
        mock_lifecycle = Mock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.register_before_message_generation.assert_called_once_with(
            self.plugin.before_message_generation
        )


if __name__ == "__main__":
    unittest.main()
