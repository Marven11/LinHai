"""测试目录更改检测插件。"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from linhai.plugin import DirectoryChangePlugin
from linhai.agent.base import PathPrompt, GlobalPrompt
from linhai.registry import Registry


class TestDirectoryChangePlugin(unittest.TestCase):
    """测试目录更改检测插件。"""

    def setUp(self):
        """设置测试环境。"""
        self.registry = Registry()
        self.plugin = DirectoryChangePlugin(self.registry)

        self.temp_dir = tempfile.mkdtemp()
        self.conversation_temp_dir = tempfile.mkdtemp()  # 专门为conversation_folder创建
        self.original_cwd = os.getcwd()

        self.mock_agent = MagicMock()
        self.mock_agent.context = {"enable_directory_change_detection": False}

        from linhai.agent.message import AgentMessage
        from linhai.llm import UserMessage, AssistantMessage, SystemMessage
        from linhai.tool.main import ToolManager

        # 为SystemMessage初始化提供mock的tool_manager
        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []

        def get_member_typechecked_side_effect(member_type, _member_class=None):
            if member_type == "tool_manager":
                return mock_tool_manager
            elif member_type == "agent":
                return self.mock_agent
            elif member_type == "conversation_folder":
                from pathlib import Path

                return Path(self.conversation_temp_dir)  # 直接返回已创建的路径
            raise RuntimeError(f"{member_type!r} not exists")

        self.registry.get_member_typechecked = Mock(
            side_effect=get_member_typechecked_side_effect
        )

        init_messages = [
            SystemMessage(
                registry=self.registry,
            ),
            UserMessage(message="Initial message"),
        ]
        self.mock_agent.message_processor = AgentMessage(self.registry, init_messages)
        # 创建消息列表并模拟异步方法
        self.messages = init_messages

        async def add_new_message(message):
            self.messages.append(message)
            return None

        self.mock_agent.message_processor.add_new_message = AsyncMock(
            side_effect=add_new_message
        )
        self.mock_agent.message_processor.get_messages = Mock(
            return_value=self.messages
        )

        self.get_member_typechecked_patch = patch.object(
            self.registry, "get_member_typechecked", return_value=self.mock_agent
        )
        self.mock_get_members = self.get_member_typechecked_patch.start()

        # Mock save_context and save_cleaned_messages to avoid actual file writes
        self.save_context_patch = patch("linhai.agent.message.save_context")
        self.mock_save_context = self.save_context_patch.start()
        self.save_cleaned_messages_patch = patch(
            "linhai.agent.conversation.save_cleaned_messages"
        )
        self.mock_save_cleaned_messages = self.save_cleaned_messages_patch.start()

    def tearDown(self):
        """清理测试环境。"""
        os.chdir(self.original_cwd)
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if hasattr(self, "conversation_temp_dir"):
            shutil.rmtree(self.conversation_temp_dir, ignore_errors=True)
        self.get_member_typechecked_patch.stop()
        self.save_context_patch.stop()
        self.save_cleaned_messages_patch.stop()

    def test_plugin_disabled_by_default(self):
        """测试插件默认禁用。"""
        self.mock_agent.context["enable_directory_change_detection"] = False

        initial_message_count = len(self.mock_agent.message_processor.get_messages())

        import asyncio

        asyncio.run(self.plugin.before_message_generation())

        final_message_count = len(self.mock_agent.message_processor.get_messages())
        # 插件禁用时不应添加PathPrompt或GlobalPrompt
        messages = self.mock_agent.message_processor.get_messages()
        prompt_count = sum(
            1 for msg in messages if isinstance(msg, (PathPrompt, GlobalPrompt))
        )
        self.assertEqual(prompt_count, 0)  # 插件禁用时不应添加内存

    def test_plugin_enabled_no_directory_change(self):
        """测试插件启用但目录未更改。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        self.plugin.last_directory = Path.cwd()

        initial_message_count = len(self.mock_agent.message_processor.get_messages())

        import asyncio

        asyncio.run(self.plugin.before_message_generation())

        final_message_count = len(self.mock_agent.message_processor.get_messages())
        # 插件启用但目录未更改，不应添加PathPrompt或GlobalPrompt
        messages = self.mock_agent.message_processor.get_messages()
        prompt_count = sum(
            1 for msg in messages if isinstance(msg, (PathPrompt, GlobalPrompt))
        )
        self.assertEqual(prompt_count, 0)

    def test_plugin_enabled_with_directory_change(self):
        """测试插件启用且目录更改。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        os.chdir(self.temp_dir)

        import asyncio

        asyncio.run(self.plugin.before_message_generation())

        self.assertIsNotNone(self.plugin.last_directory)
        if self.plugin.last_directory is not None:
            self.assertEqual(
                self.plugin.last_directory.resolve(), Path(self.temp_dir).resolve()
            )

    def test_plugin_detects_target_files(self):
        """测试插件检测目标文件。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        test_file = Path(self.temp_dir) / "AGENTS.md"
        test_file.write_text("# Test Prompt\n\nTest content")

        os.chdir(self.temp_dir)

        import asyncio

        asyncio.run(self.plugin.before_message_generation())

        messages = self.mock_agent.message_processor.get_messages()
        pathprompt_count = sum(1 for msg in messages if isinstance(msg, PathPrompt))
        self.assertEqual(pathprompt_count, 1)
        pathprompt_msg = next(msg for msg in messages if isinstance(msg, PathPrompt))
        self.assertEqual(pathprompt_msg.filepath.resolve(), test_file.resolve())

    def test_plugin_avoids_duplicates(self):
        """测试插件避免重复添加相同路径的消息。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        test_file = Path(self.temp_dir) / "AGENTS.md"
        test_file.write_text("# Test Prompt\n\nTest content")

        os.chdir(self.temp_dir)

        existing_prompt = PathPrompt(test_file)
        import asyncio

        asyncio.run(self.mock_agent.message_processor.add_new_message(existing_prompt))

        import asyncio

        asyncio.run(self.plugin.before_message_generation())

        pathprompt_count = sum(
            1
            for msg in self.mock_agent.message_processor.get_messages()
            if isinstance(msg, PathPrompt)
        )
        self.assertEqual(pathprompt_count, 1)

    def test_plugin_handles_global_prompt_duplicates(self):
        """测试插件避免与GlobalPrompt重复。"""
        self.mock_agent.context["enable_directory_change_detection"] = True

        test_file = Path(self.temp_dir) / "AGENTS.md"
        test_file.write_text("# Test Prompt\n\nTest content")

        os.chdir(self.temp_dir)

        existing_prompt = GlobalPrompt(test_file)
        import asyncio

        asyncio.run(self.mock_agent.message_processor.add_new_message(existing_prompt))

        import asyncio

        asyncio.run(self.plugin.before_message_generation())

        prompt_count = sum(
            1
            for msg in self.mock_agent.message_processor.get_messages()
            if isinstance(msg, (PathPrompt, GlobalPrompt))
        )
        self.assertEqual(prompt_count, 1)

    def test_plugin_registers_correctly(self):
        """测试插件正确注册到生命周期。"""
        mock_lifecycle = Mock()

        self.plugin.register(mock_lifecycle)

        mock_lifecycle.register_before_message_generation.assert_called_once_with(
            self.plugin.before_message_generation
        )


if __name__ == "__main__":
    unittest.main()
