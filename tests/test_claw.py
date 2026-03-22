"""测试claw功能"""

import asyncio
import unittest
import tempfile
import shutil
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

from linhai.agent.create import _create_pinned_messages, AgentBuildContext
from linhai.agent.base import RuntimeMessage, FileContentMessage
from linhai.plugin.claw import ClawPlugin


class TestClawInitialization(unittest.TestCase):
    """测试claw初始化功能"""

    def test_initialize_claw_files(self):
        """测试_initialize_claw_files()从prompt.py常量读取并写入文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            claw_dir = Path(tmpdir) / "claw"
            claw_dir.mkdir(parents=True, exist_ok=True)

            mock_group_chat = Mock()
            mock_cli_args = Mock()
            mock_cli_args.claw_folder = str(claw_dir)
            plugin = ClawPlugin(mock_group_chat, mock_cli_args)
            plugin._initialize_claw_files()

            self.assertTrue((claw_dir / "AGENTS.md").exists())
            self.assertTrue((claw_dir / "REMINDER.md").exists())

            agents_content = (claw_dir / "AGENTS.md").read_text(encoding="utf-8")
            self.assertGreater(len(agents_content), 100)

            reminder_content = (claw_dir / "REMINDER.md").read_text(encoding="utf-8")
            self.assertIn("务必优先遵守AGENTS.md和SOUL.md", reminder_content)

    def test_initialize_claw_files_handles_missing_prompt(self):
        """测试prompt.md不存在时不报错"""
        with tempfile.TemporaryDirectory() as tmpdir:
            claw_dir = Path(tmpdir) / "claw"
            claw_dir.mkdir(parents=True, exist_ok=True)

            mock_group_chat = Mock()
            mock_cli_args = Mock()
            mock_cli_args.claw_folder = str(claw_dir)
            plugin = ClawPlugin(mock_group_chat, mock_cli_args)

            plugin._initialize_claw_files()


class TestClawPinnedMessages(unittest.TestCase):
    """测试pinned messages中的claw内容添加"""

    def setUp(self):
        self.temp_home = tempfile.mkdtemp()
        self.home_path = Path(self.temp_home)

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    async def _create_test_context(self, claw=False, create_files=True):
        """创建测试用的context"""
        if create_files:
            claw_dir = self.home_path / ".local" / "share" / "linhai" / "claw"
            claw_dir.mkdir(parents=True, exist_ok=True)
            (claw_dir / "AGENTS.md").write_text("# AGENTS内容", encoding="utf-8")
            (claw_dir / "SOUL.md").write_text("# SOUL内容", encoding="utf-8")

        mock_config = Mock()
        mock_config.memory = None

        mock_context_dict = {
            "group_chat": Mock(),
            "config": mock_config,
            "config_basedir": None,
            "llm_name": "test-llm",
            "max_toolcall_token_in_round": 30000,
            "checklist_path": None,
            "planning": False,
            "cli_args": Mock(claw=claw, message=None, file=None),
        }
        context = cast(AgentBuildContext, mock_context_dict)

        with patch("pathlib.Path.home", return_value=self.home_path):
            messages = await _create_pinned_messages(context)
            return messages

    def test_claw_content_not_added_when_not_claw(self):
        """测试非claw模式时不添加claw内容"""
        messages = asyncio.run(self._create_test_context(claw=False, create_files=True))

        claw_intro_found = any(
            isinstance(msg, RuntimeMessage) and "CLAW模式介绍" in str(msg)
            for msg in messages
        )
        self.assertFalse(claw_intro_found, "非claw模式不应添加CLAW介绍")

    def test_claw_content_added_when_claw_and_dir_exists(self):
        """测试claw模式且目录存在时，claw内容由插件添加，不在_create_pinned_messages中"""
        messages = asyncio.run(self._create_test_context(claw=True, create_files=True))

        claw_intro_found = any(
            isinstance(msg, RuntimeMessage) and "CLAW模式介绍" in str(msg)
            for msg in messages
        )
        self.assertFalse(
            claw_intro_found, "claw内容现在由插件添加，不在_create_pinned_messages中"
        )

        file_content_found = any(
            isinstance(msg, FileContentMessage) for msg in messages
        )
        self.assertFalse(file_content_found, "claw文件内容现在由插件添加")

        file_msgs = [msg for msg in messages if isinstance(msg, FileContentMessage)]
        self.assertEqual(len(file_msgs), 0, f"应有0个文件消息，实际{len(file_msgs)}")

    def test_claw_content_not_added_when_claw_but_dir_not_exists(self):
        """测试claw模式但目录不存在时不添加claw内容"""
        claw_dir = self.home_path / ".local" / "share" / "linhai" / "claw"
        if claw_dir.exists():
            shutil.rmtree(claw_dir)

        messages = asyncio.run(self._create_test_context(claw=True, create_files=False))

        claw_intro_found = any(
            isinstance(msg, RuntimeMessage) and "CLAW模式介绍" in str(msg)
            for msg in messages
        )
        self.assertFalse(claw_intro_found, "claw目录不存在时不应添加CLAW介绍")


if __name__ == "__main__":
    unittest.main()
