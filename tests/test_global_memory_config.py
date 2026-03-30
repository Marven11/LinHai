"""测试全局指导配置功能"""

import tempfile
import shutil
import os
from pathlib import Path
import unittest
import asyncio

from linhai.agent.create import _create_pinned_messages
from linhai.registry import Registry
from linhai.agent.base import GlobalPrompt


class TestGlobalPromptConfig(unittest.TestCase):
    """测试全局指导配置"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir()
        self.working_dir = Path(self.temp_dir) / "working"
        self.working_dir.mkdir()

        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        self.registry = Registry()

        from linhai.tool.main import ToolManager
        from unittest.mock import Mock
        import argparse

        mock_tool_manager = Mock(spec=ToolManager)
        mock_tool_manager.get_tools_info.return_value = []
        self.registry.register_member("tool_manager", mock_tool_manager)

        self.mock_cli_args = argparse.Namespace()
        self.mock_cli_args.message = None
        self.mock_cli_args.file = None
        self.mock_cli_args.claw = False
        self.mock_cli_args.claw_folder = None
        self.registry.register_member("cli_args", self.mock_cli_args)

    def tearDown(self):
        """测试后清理"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)

    def test_prompt_file_path_absolute(self):
        """测试绝对路径的全局指导文件"""
        prompt_file = Path(self.temp_dir) / "custom_prompt.md"
        prompt_file.write_text("# 自定义全局指导\n- 测试内容")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from unittest.mock import Mock

            mock_config = Mock()
            mock_prompt = Mock()
            mock_prompt.file_path = str(prompt_file.relative_to(prompt_file.parent))
            mock_config.user_prompt = mock_prompt

            context = {
                "registry": self.registry,
                "config": mock_config,
                "config_basedir": prompt_file.parent,
                "llms": [],
                "llm_name": None,
                "checklist_path": None,
                "cli_args": self.mock_cli_args,
                "user_prompt": prompt_file,
                "max_toolcall_token_in_round": 0.3,
                "planning": False,
            }
            init_messages = loop.run_until_complete(_create_pinned_messages(context))

            prompt_messages = [
                msg for msg in init_messages if isinstance(msg, GlobalPrompt)
            ]
            self.assertGreater(len(prompt_messages), 0)

            custom_prompt_found = False
            for msg in prompt_messages:
                if isinstance(msg, GlobalPrompt) and msg.filepath == prompt_file:
                    custom_prompt_found = True
                    break

            self.assertTrue(custom_prompt_found, "未找到自定义全局指导文件")

        finally:
            loop.close()

    def test_prompt_file_path_relative(self):
        """测试相对路径的全局指导文件"""
        prompt_file = Path("./") / "test_relative_prompt.md"
        prompt_file.write_text("# 相对路径全局指导\n- 测试内容")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from unittest.mock import Mock

            mock_config = Mock()
            mock_prompt = Mock()
            mock_prompt.file_path = "test_relative_prompt.md"
            mock_config.user_prompt = mock_prompt

            context = {
                "registry": self.registry,
                "config": mock_config,
                "config_basedir": Path(".").absolute(),
                "llms": [],
                "llm_name": None,
                "checklist_path": None,
                "cli_args": self.mock_cli_args,
                "user_prompt": str(Path("./").absolute() / "test_relative_prompt.md"),
                "max_toolcall_token_in_round": 0.3,
                "planning": False,
            }
            init_messages = loop.run_until_complete(_create_pinned_messages(context))

            prompt_messages = [
                msg for msg in init_messages if isinstance(msg, GlobalPrompt)
            ]
            self.assertGreater(len(prompt_messages), 0)

            relative_prompt_found = False
            for msg in prompt_messages:
                if (
                    isinstance(msg, GlobalPrompt)
                    and msg.filepath.name == "test_relative_prompt.md"
                ):
                    relative_prompt_found = True
                    self.assertTrue(msg.filepath.exists(), "相对路径文件不存在")
                    break

            self.assertTrue(relative_prompt_found, "未找到相对路径全局指导文件")

        finally:
            loop.close()
            if prompt_file.exists():
                prompt_file.unlink()

    def test_prompt_file_path_none(self):
        """测试未提供prompt_file_path时使用默认路径"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            from unittest.mock import Mock

            mock_config = Mock()
            mock_config.user_prompt = None

            context = {
                "registry": self.registry,
                "config": mock_config,
                "config_basedir": None,
                "llms": [],
                "llm_name": None,
                "checklist_path": None,
                "cli_args": self.mock_cli_args,
                "user_prompt": None,
                "max_toolcall_token_in_round": 0.3,
                "planning": False,
            }
            init_messages = loop.run_until_complete(_create_pinned_messages(context))

            prompt_messages = [
                msg for msg in init_messages if isinstance(msg, GlobalPrompt)
            ]
            self.assertGreater(len(prompt_messages), 0)

            default_prompt_found = False
            default_path = Path("~/.config/linhai/AGENTS.md").expanduser()
            for msg in prompt_messages:
                if isinstance(msg, GlobalPrompt) and msg.filepath == default_path:
                    default_prompt_found = True
                    break

            self.assertTrue(default_prompt_found, "未找到默认全局指导文件")

        finally:
            loop.close()

    def test_project_prompt_files(self):
        """测试项目记忆文件自动加载"""
        project_files = ["AGENTS.md", "AGENT.md", "CLAUDE.md"]
        created_files = []

        try:
            for filename in project_files:
                file_path = Path("./") / filename
                file_path.write_text(f"# {filename}\n- 测试内容")
                created_files.append(file_path)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                from unittest.mock import Mock

                mock_config = Mock()
                mock_config.user_prompt = None

                context = {
                    "registry": self.registry,
                    "config": mock_config,
                    "config_basedir": Path(".").absolute(),
                    "llms": [],
                    "llm_name": None,
                    "checklist_path": None,
                    "cli_args": self.mock_cli_args,
                    "user_prompt": None,
                    "max_toolcall_token_in_round": 0.3,
                    "planning": False,
                }
                init_messages = loop.run_until_complete(
                    _create_pinned_messages(context)
                )

                prompt_messages = [
                    msg for msg in init_messages if isinstance(msg, GlobalPrompt)
                ]

                for filename in project_files:
                    file_found = False
                    for msg in prompt_messages:
                        if (
                            isinstance(msg, GlobalPrompt)
                            and msg.filepath.name == filename
                        ):
                            file_found = True
                            break
                    if not file_found:
                        file_path = Path("./") / filename
                        if file_path.exists():
                            file_found = True
                    self.assertTrue(file_found, f"未找到项目记忆文件: {filename}")

            finally:
                loop.close()

        finally:
            for file_path in created_files:
                if file_path.exists():
                    file_path.unlink()


if __name__ == "__main__":
    unittest.main()
