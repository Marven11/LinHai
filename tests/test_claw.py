"""测试claw功能"""

import asyncio
import unittest
import tempfile
import shutil
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

from linhai.agent.create import init_claw, _create_pinned_messages, AgentBuildContext
from linhai.agent.base import RuntimeMessage, FileContentMessage


class TestClawFunction(unittest.TestCase):
    """测试claw核心功能"""

    def test_init_claw_creates_directory_and_files(self):
        """测试init_claw()正确创建目录和五个核心文档"""
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir)
            claw_dir = home_dir / ".local" / "share" / "linhai" / "claw"

            with patch("pathlib.Path.home", return_value=home_dir):
                init_claw()

                self.assertTrue(claw_dir.exists())
                self.assertTrue(claw_dir.is_dir())

                core_files = [
                    "AGENTS.md",
                    "BOOTSTRAP.md",
                    "IDENTITY.md",
                    "SOUL.md",
                    "USER.md",
                ]

                for filename in core_files:
                    file_path = claw_dir / filename
                    self.assertTrue(file_path.exists())
                    self.assertTrue(file_path.is_file())
                    content = file_path.read_text(encoding="utf-8")
                    self.assertGreater(len(content), 100)

    def test_init_claw_does_not_overwrite_existing_files(self):
        """测试init_claw()不覆盖已存在的文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir)
            claw_dir = home_dir / ".local" / "share" / "linhai" / "claw"
            claw_dir.mkdir(parents=True, exist_ok=True)

            test_file = claw_dir / "AGENTS.md"
            original_content = "# 测试内容"
            test_file.write_text(original_content, encoding="utf-8")

            with patch("pathlib.Path.home", return_value=home_dir):
                init_claw()

                self.assertEqual(
                    test_file.read_text(encoding="utf-8"), original_content
                )


class TestClawPinnedMessages(unittest.TestCase):
    """测试pinned messages中的claw内容添加"""

    def setUp(self):
        # 创建临时目录模拟home
        self.temp_home = tempfile.mkdtemp()
        self.home_path = Path(self.temp_home)

    def tearDown(self):
        shutil.rmtree(self.temp_home, ignore_errors=True)

    async def _create_test_context(self, claw=False, create_files=True):
        """创建测试用的context"""
        # 创建claw目录和文件（如果需要）
        if create_files:
            claw_dir = self.home_path / ".local" / "share" / "linhai" / "claw"
            claw_dir.mkdir(parents=True, exist_ok=True)
            (claw_dir / "AGENTS.md").write_text("# AGENTS内容", encoding="utf-8")
            (claw_dir / "SOUL.md").write_text("# SOUL内容", encoding="utf-8")

        # 创建mock context，使用cast确保类型正确
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
        # 使用cast让pyright满意
        context = cast(AgentBuildContext, mock_context_dict)

        # 使用patch替换Path.home返回我们的临时home
        with patch("pathlib.Path.home", return_value=self.home_path):
            messages = await _create_pinned_messages(context)
            return messages

    def test_claw_content_not_added_when_not_claw(self):
        """测试非claw模式时不添加claw内容"""
        messages = asyncio.run(self._create_test_context(claw=False, create_files=True))

        # 检查是否有CLAW模式介绍
        claw_intro_found = any(
            isinstance(msg, RuntimeMessage) and "CLAW模式介绍" in str(msg)
            for msg in messages
        )
        self.assertFalse(claw_intro_found, "非claw模式不应添加CLAW介绍")

    def test_claw_content_added_when_claw_and_dir_exists(self):
        """测试claw模式且目录存在时，claw内容由插件添加，不在_create_pinned_messages中"""
        messages = asyncio.run(self._create_test_context(claw=True, create_files=True))

        # CLAW模式介绍不再通过_create_pinned_messages添加，而是由插件添加
        claw_intro_found = any(
            isinstance(msg, RuntimeMessage) and "CLAW模式介绍" in str(msg)
            for msg in messages
        )
        self.assertFalse(
            claw_intro_found, "claw内容现在由插件添加，不在_create_pinned_messages中"
        )

        # 文件内容也不再通过_create_pinned_messages添加
        file_content_found = any(
            isinstance(msg, FileContentMessage) for msg in messages
        )
        self.assertFalse(file_content_found, "claw文件内容现在由插件添加")

        # 应该没有文件内容消息
        file_msgs = [msg for msg in messages if isinstance(msg, FileContentMessage)]
        self.assertEqual(len(file_msgs), 0, f"应有0个文件消息，实际{len(file_msgs)}")

    def test_claw_content_not_added_when_claw_but_dir_not_exists(self):
        """测试claw模式但目录不存在时不添加claw内容"""
        # 确保claw目录不存在
        claw_dir = self.home_path / ".local" / "share" / "linhai" / "claw"
        if claw_dir.exists():
            shutil.rmtree(claw_dir)

        messages = asyncio.run(self._create_test_context(claw=True, create_files=False))

        # 不应该有CLAW模式介绍，因为目录不存在
        claw_intro_found = any(
            isinstance(msg, RuntimeMessage) and "CLAW模式介绍" in str(msg)
            for msg in messages
        )
        self.assertFalse(claw_intro_found, "claw目录不存在时不应添加CLAW介绍")


class TestClawFolderOption(unittest.TestCase):
    """测试--claw-folder选项功能"""

    def test_init_claw_with_custom_directory(self):
        """测试init_claw()使用自定义目录参数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom_claw"

            init_claw(claw_dir=custom_dir)

            self.assertTrue(custom_dir.exists())
            self.assertTrue(custom_dir.is_dir())

            core_files = [
                "AGENTS.md",
                "BOOTSTRAP.md",
                "IDENTITY.md",
                "SOUL.md",
                "USER.md",
            ]

            for filename in core_files:
                file_path = custom_dir / filename
                self.assertTrue(file_path.exists())
                self.assertTrue(file_path.is_file())
                content = file_path.read_text(encoding="utf-8")
                self.assertGreater(len(content), 100)

    def test_init_claw_default_and_custom_separate(self):
        """测试默认目录和自定义目录互不干扰"""
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir)
            default_dir = home_dir / ".local" / "share" / "linhai" / "claw"
            custom_dir = home_dir / "custom_claw"

            with patch("pathlib.Path.home", return_value=home_dir):
                init_claw()
                self.assertTrue(default_dir.exists())
                self.assertFalse(custom_dir.exists())

            init_claw(claw_dir=custom_dir)
            self.assertTrue(custom_dir.exists())

            self.assertTrue(default_dir.exists())
            self.assertTrue(custom_dir.exists())

    def test_init_claw_with_nonexistent_parent_directory(self):
        """测试在不存在的父目录中创建claw目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "deep" / "deeper" / "custom_claw"

            init_claw(claw_dir=custom_dir)

            self.assertTrue(custom_dir.exists())
            self.assertTrue(custom_dir.is_dir())

    def test_init_claw_does_not_overwrite_existing_custom_directory(self):
        """测试init_claw()不覆盖已存在的自定义目录文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom_claw"
            custom_dir.mkdir(parents=True, exist_ok=True)

            test_file = custom_dir / "AGENTS.md"
            original_content = "# 自定义内容"
            test_file.write_text(original_content, encoding="utf-8")

            init_claw(claw_dir=custom_dir)

            self.assertEqual(test_file.read_text(encoding="utf-8"), original_content)


if __name__ == "__main__":
    unittest.main()
