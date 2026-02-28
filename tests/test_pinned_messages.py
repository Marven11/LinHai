#!/usr/bin/env python3
"""测试pinned messages和历史压缩逻辑。"""

import unittest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import argparse

from linhai.agent.create import _create_pinned_messages, AgentBuildContext
from linhai.group_chat import GroupChat
from linhai.llm import SystemMessage, UserMessage
from linhai.agent.base import (
    GlobalPrompt,
    PathPrompt,
    FileContentMessage,
    ChecklistMessage,
    RuntimeMessage,
)
from linhai.agent.base import MessagesListSummerizeMessage


class TestPinnedMessages(unittest.IsolatedAsyncioTestCase):
    """测试pinned messages创建逻辑。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        # 注册必要的成员
        from linhai.tool.main import ToolManager

        mock_tool_manager = MagicMock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.group_chat.register_member("tool_manager", mock_tool_manager)

        # 创建模拟配置
        self.config = MagicMock()
        self.config.agent = MagicMock()
        self.config.tools = MagicMock()
        self.config.agent.mcp = MagicMock()

        # 创建模拟cli_args
        self.cli_args = argparse.Namespace()
        self.cli_args.message = []
        self.cli_args.file = []
        self.cli_args.claw = False

        # 基础目录
        self.config_basedir = Path("/tmp/test")

        # 模拟Path.exists()为False，确保项目记忆文件不存在
        self.exists_patcher = patch("pathlib.Path.exists", return_value=False)
        self.mock_exists = self.exists_patcher.start()

    def tearDown(self):
        """清理测试环境。"""
        self.exists_patcher.stop()

    def create_context(self, prompt_config=None, checklist_path=None):
        """创建AgentBuildContext。"""
        context = {
            "group_chat": self.group_chat,
            "config": self.config,
            "config_basedir": self.config_basedir,
            "cli_args": self.cli_args,
            "checklist_path": checklist_path,
        }
        if prompt_config:
            self.config.user_prompt = prompt_config
        else:
            self.config.user_prompt = None
        return context

    async def test_pinned_messages_without_prompt_config(self):
        """测试没有prompt配置时，使用默认全局指导路径。"""
        context = self.create_context()

        pinned_messages = await _create_pinned_messages(context)

        # 应该至少包含系统消息、启动时间消息和全局指导消息
        self.assertGreaterEqual(len(pinned_messages), 3)
        self.assertIsInstance(pinned_messages[0], SystemMessage)
        self.assertIsInstance(pinned_messages[1], RuntimeMessage)
        self.assertIsInstance(pinned_messages[2], GlobalPrompt)
        # 检查GlobalPrompt的filepath属性
        self.assertIn("AGENTS.md", str(pinned_messages[2].filepath))

    async def test_pinned_messages_with_prompt_config(self):
        """测试有prompt配置时，使用配置的全局指导路径。"""
        prompt_config = Mock()()
        prompt_config.file_path = "custom_prompt.md"
        self.config.user_prompt = prompt_config

        context = self.create_context(prompt_config=prompt_config)

        pinned_messages = await _create_pinned_messages(context)

        self.assertGreaterEqual(len(pinned_messages), 3)
        self.assertIsInstance(pinned_messages[0], SystemMessage)
        self.assertIsInstance(pinned_messages[1], RuntimeMessage)
        self.assertIsInstance(pinned_messages[2], GlobalPrompt)
        # 检查GlobalPrompt的filepath属性
        expected_path = self.config_basedir / "custom_prompt.md"
        self.assertEqual(str(pinned_messages[2].filepath), str(expected_path))

    async def test_pinned_messages_with_user_messages(self):
        """测试通过-m参数添加用户消息。"""
        self.cli_args.message = ["Hello", "World"]
        context = self.create_context()

        pinned_messages = await _create_pinned_messages(context)

        # 系统消息 + 启动时间消息 + 全局指导消息 + 2条用户消息
        self.assertEqual(len(pinned_messages), 5)
        self.assertIsInstance(pinned_messages[0], SystemMessage)
        self.assertIsInstance(pinned_messages[1], RuntimeMessage)
        self.assertIsInstance(pinned_messages[2], GlobalPrompt)
        self.assertIsInstance(pinned_messages[3], UserMessage)
        self.assertIsInstance(pinned_messages[4], UserMessage)
        self.assertEqual(pinned_messages[3].message, "Hello")
        self.assertEqual(pinned_messages[4].message, "World")

    async def test_pinned_messages_with_file_messages(self):
        """测试通过-f参数添加文件内容消息。"""
        # 创建临时文件
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("File content")
            temp_file_path = Path(f.name)

        try:
            self.cli_args.file = [temp_file_path]
            context = self.create_context()

            pinned_messages = await _create_pinned_messages(context)

            # 系统消息 + 启动时间消息 + 全局指导消息 + 文件内容消息
            self.assertEqual(len(pinned_messages), 4)
            self.assertIsInstance(pinned_messages[0], SystemMessage)
            self.assertIsInstance(pinned_messages[1], RuntimeMessage)
            self.assertIsInstance(pinned_messages[2], GlobalPrompt)
            self.assertIsInstance(pinned_messages[3], FileContentMessage)
            self.assertEqual(pinned_messages[3].content, "File content")
        finally:
            temp_file_path.unlink()

    async def test_pinned_messages_with_checklist(self):
        """测试通过检查清单路径添加ChecklistMessage。"""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Checklist")
            checklist_path = Path(f.name)

        try:
            context = self.create_context(checklist_path=checklist_path)

            pinned_messages = await _create_pinned_messages(context)

            # 系统消息 + 启动时间消息 + 全局指导消息 + ChecklistMessage
            self.assertEqual(len(pinned_messages), 4)
            self.assertIsInstance(pinned_messages[0], SystemMessage)
            self.assertIsInstance(pinned_messages[1], RuntimeMessage)
            self.assertIsInstance(pinned_messages[2], GlobalPrompt)
            self.assertIsInstance(pinned_messages[3], ChecklistMessage)
        finally:
            checklist_path.unlink()

    @patch("pathlib.Path.exists", side_effect=lambda: True)
    async def test_pinned_messages_with_project_prompt_files(self, mock_exists):
        """测试项目记忆文件（如果存在）。"""
        context = self.create_context()

        pinned_messages = await _create_pinned_messages(context)

        # 系统消息 + 启动时间消息 + 全局指导消息 + 可能的PathPrompt
        self.assertGreaterEqual(len(pinned_messages), 4)
        self.assertIsInstance(pinned_messages[0], SystemMessage)
        self.assertIsInstance(pinned_messages[1], RuntimeMessage)
        self.assertIsInstance(pinned_messages[2], GlobalPrompt)
        # 检查是否有PathPrompt
        path_messages = [msg for msg in pinned_messages if isinstance(msg, PathPrompt)]
        self.assertGreaterEqual(len(path_messages), 1)

    @patch("linhai.agent.workflow._prepare_messages_for_compression")
    async def test_context_forget_range_step1_generates_id(self, mock_prepare):
        """测试context_forget_range_step1生成range_clean_id。"""
        # 模拟group_chat和agent
        mock_group_chat = MagicMock()
        mock_agent = MagicMock()
        mock_message_processor = MagicMock()
        mock_agent.message_processor = mock_message_processor

        # 模拟消息列表
        mock_message_processor.messages = []

        # 模拟RangeCleanManager
        mock_range_clean_manager = MagicMock()
        mock_range_clean_manager.create_clean_info = MagicMock()

        # 设置group_chat.get_member_typechecked的返回值
        def get_member_typechecked_side_effect(name, cls):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            else:
                return MagicMock()

        mock_group_chat.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        # 模拟filter_messages和add_new_message
        mock_message_processor.filter_messages = AsyncMock()
        mock_message_processor.add_new_message = AsyncMock()

        # 模拟send_if_exists为异步函数
        mock_group_chat.send_if_exists = AsyncMock()

        # 模拟_prepare_messages_for_compression返回一个字符串
        mock_prepare.return_value = "消息总结"

        # 模拟generate_id返回一个固定ID
        with patch(
            "linhai.agent.workflow.generate_id", return_value="test_range_clean_id"
        ):
            from linhai.agent.workflow import context_forget_range_step1

            result = await context_forget_range_step1(mock_group_chat)

            # 验证结果
            self.assertEqual(
                result.content,
                "已生成消息列表总结，ID: test_range_clean_id，当前共有0条消息。请查看消息列表总结后调用context_forget_range_step2进行删除。",
            )

            # 验证create_clean_info被调用
            mock_range_clean_manager.create_clean_info.assert_called_once_with(
                "test_range_clean_id", 0, 0
            )

            # 验证add_new_message被调用
            mock_message_processor.add_new_message.assert_called_once()

    @patch("linhai.agent.workflow._validate_compression_range")
    @patch("linhai.agent.workflow.save_cleaned_messages")
    async def test_context_forget_range_step2_validates_and_deletes(
        self, mock_save, mock_validate
    ):
        """测试context_forget_range_step2验证range_clean_id并删除消息。"""
        # 模拟group_chat和agent
        mock_group_chat = MagicMock()
        mock_agent = MagicMock()
        mock_message_processor = MagicMock()
        mock_agent.message_processor = mock_message_processor

        # 模拟消息列表，至少有100条消息，这样max_allowed_id才不会为负数
        # 同时添加一个MessagesListSummerizeMessage，以便删除
        mock_summary_message = MagicMock(spec=MessagesListSummerizeMessage)
        mock_summary_message.range_clean_id = "test_id"
        mock_summary_message.invalidate = MagicMock()
        mock_message_processor.messages = [mock_summary_message] + [
            MagicMock() for _ in range(99)
        ]

        # 模拟RangeCleanManager和RangeCleanInfo
        mock_range_clean_manager = MagicMock()
        mock_info = MagicMock()
        mock_info.message_length = 100
        mock_info.min_safe_id = 10
        mock_range_clean_manager.get_clean_info.return_value = mock_info
        mock_range_clean_manager.remove_clean_info = MagicMock()

        # 设置group_chat.get_member_typechecked的返回值
        def get_member_typechecked_side_effect(name, cls):
            if name == "agent":
                return mock_agent
            elif name == "range_clean_manager":
                return mock_range_clean_manager
            else:
                return MagicMock()

        mock_group_chat.get_member_typechecked.side_effect = (
            get_member_typechecked_side_effect
        )

        # 模拟删除消息函数：第一次调用返回空列表（删除MessagesListSummerizeMessage），
        # 第二次调用返回包含一个UserMessage的列表
        mock_user_message = MagicMock(spec=UserMessage)
        mock_user_message.message = "测试用户消息"
        mock_message_processor.delete_message_range = AsyncMock(
            side_effect=[[], [mock_user_message]]
        )
        mock_message_processor.insert_message = AsyncMock()

        # 模拟Path和save_cleaned_messages
        mock_conversation_dir = MagicMock(spec=Path)
        mock_group_chat.get_member_typechecked.return_value = mock_conversation_dir

        # 模拟_validate_compression_range返回成功
        mock_validate.return_value = (True, "")

        # 模拟save_cleaned_messages什么都不做
        mock_save.return_value = None

        from linhai.agent.workflow import context_forget_range_step2

        # 调用函数
        result = await context_forget_range_step2(
            mock_group_chat,
            range_clean_id="test_id",
            start_id=20,
            end_id=30,
            description="测试压缩",
        )

        # 验证结果
        self.assertEqual(
            result.content,
            "你使用历史压缩删除（遗忘）了一段消息，被转储到了None中，请根据**历史压缩总结**明确当前任务继续工作",
        )

        # 验证get_clean_info被调用
        mock_range_clean_manager.get_clean_info.assert_called_once_with("test_id")

        # 验证delete_message_range被调用两次
        self.assertEqual(mock_message_processor.delete_message_range.call_count, 2)

        # 验证remove_clean_info被调用
        mock_range_clean_manager.remove_clean_info.assert_called_once_with("test_id")

        # 验证insert_message被调用两次（一次插入RuntimeMessage描述删除的用户消息，一次插入描述）
        self.assertEqual(mock_message_processor.insert_message.call_count, 2)

    async def test_pinned_messages_includes_startup_time(self):
        """测试pinned messages包含启动时间。"""
        context = self.create_context()

        pinned_messages = await _create_pinned_messages(context)

        # 应该至少包含：SystemMessage + RuntimeMessage(启动时间) + GlobalPrompt
        self.assertGreaterEqual(len(pinned_messages), 3)
        self.assertIsInstance(pinned_messages[0], SystemMessage)

        # 检查第二条消息是RuntimeMessage且包含启动时间
        self.assertIsInstance(pinned_messages[1], RuntimeMessage)
        runtime_message = pinned_messages[1]
        self.assertIn("Agent启动时间:", runtime_message.message)

        # 验证时间格式 YYYY-MM-DD HH:MM:SS
        import re

        time_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        match = re.search(time_pattern, runtime_message.message)
        self.assertIsNotNone(match, f"时间格式不正确: {runtime_message.message}")

        # 第三条消息应该是GlobalPrompt
        self.assertIsInstance(pinned_messages[2], GlobalPrompt)


if __name__ == "__main__":
    unittest.main()
