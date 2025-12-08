"""测试Git diff审查插件。"""

import unittest
from unittest.mock import Mock, patch, mock_open
import asyncio
from typing import cast

from linhai.subagent.types.git_diff_reviewer import GitDiffReviewPlugin
from linhai.group_chat import GroupChat


class TestGitDiffReviewPlugin(unittest.TestCase):
    """测试GitDiffReviewPlugin。"""

    def setUp(self):
        """设置测试环境。"""
        self.group_chat = GroupChat()
        self.plugin = GitDiffReviewPlugin(self.group_chat)
        self.agent = Mock()
        self.agent.current_answer = None
        self.agent.message_processor = Mock()
        self.agent.message_processor.get_messages = Mock(return_value=[])
        
        self.plugin._agent_used_file_modification_tools = False
        
        self.mock_git_diff = "diff --git a/test.py b/test.py\n+print('hello')"
        self.mock_empty = ""
        self.mock_status_empty = ""
        self.mock_status_deleted = " D deleted_file.py"
        
        from linhai.subagent import SubAgentManager
        self.subagent_manager = Mock(spec=SubAgentManager)
        self.subagent_manager.subagent_config = None  # 默认不启用
        self.group_chat.register_member("subagent_manager", self.subagent_manager)
        
        from linhai.tool.general import TodolistManager
        self.todolist_manager = Mock(spec=TodolistManager)
        self.todolist_manager.list_todolists = Mock(return_value=[])
        self.group_chat.register_member("todolist_manager", self.todolist_manager)
        
        # 注册cli_args mock
        import argparse
        from pathlib import Path
        self.cli_args = Mock(spec=argparse.Namespace)
        # 创建一个临时文件路径作为code_style
        import tempfile
        self.temp_code_style_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False)
        self.temp_code_style_file.write("# 代码风格要求\n")
        self.temp_code_style_file.close()
        # 将code_style设置为Path对象
        self.cli_args.code_style = Path(self.temp_code_style_file.name)
        self.group_chat.register_member("cli_args", self.cli_args)

    def _setup_subagent_manager(self):
        """设置SubAgentManager的mock。"""
        from linhai.subagent import SubAgentManager
        from linhai.config import SubAgentConfig, EnabledAgentTypes
        try:
            subagent_manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
        except RuntimeError:
            subagent_manager = Mock(spec=SubAgentManager)
            self.group_chat.register_member("subagent_manager", subagent_manager)
        subagent_config = Mock(spec=SubAgentConfig)
        subagent_config.enable = True
        enabled_agent_types = Mock(spec=EnabledAgentTypes)
        enabled_agent_types.git_diff_reviewer = True  # 启用git_diff_reviewer
        subagent_config.enabled_agent_types = enabled_agent_types
        subagent_manager.subagent_config = subagent_config
        subagent_manager.create_subagent = Mock(return_value="success")
        return subagent_manager

    def _setup_for_review(self):
        """设置审查条件：Agent使用了文件修改工具。"""
        self.plugin._agent_used_file_modification_tools = True

    def _setup_git_mocks(self, mock_exists, mock_run, git_diff=None, ls_files_output=None):
        """设置git相关命令的mock。"""
        mock_exists.return_value = True
        
        if git_diff is None:
            git_diff = self.mock_git_diff
        if ls_files_output is None:
            ls_files_output = ""
            
        mock_run.side_effect = [
            Mock(stdout=git_diff, returncode=0),      # git diff --cached
            Mock(stdout=self.mock_empty, returncode=0), # git diff
            Mock(stdout=ls_files_output, returncode=0)  # git ls-files --others --exclude-standard
        ]

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        self.assertIsInstance(self.plugin, GitDiffReviewPlugin)
        self.assertEqual(self.plugin.group_chat, self.group_chat)
        self.assertEqual(self.plugin._agent_used_file_modification_tools, False)

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_git_repo(self, mock_exists, mock_run):
        """测试不在git仓库时不启动审查。"""
        mock_exists.return_value = False
        
        self._setup_subagent_manager()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()  # 会被调用3次：.git, TODO.md, LINHAI.md
        mock_run.assert_not_called()

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_diff(self, mock_exists, mock_run):
        """测试没有git diff时不启动审查。"""
        mock_exists.return_value = True
        mock_run.return_value = Mock(stdout="", returncode=0)
        
        self._setup_subagent_manager()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()  # 会被调用3次：.git, TODO.md, LINHAI.md
        mock_run.assert_called()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_with_diff(self, mock_exists, mock_run, mock_create_task):
        """测试有git diff时启动审查。"""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(stdout="diff --git a/test.py b/test.py\n+print('hello')", returncode=0),
            Mock(stdout="", returncode=0),
            Mock(stdout="", returncode=0)
        ]
        
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()  # 会被调用3次：.git, TODO.md, LINHAI.md
        mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_change(self, mock_exists, mock_run, mock_create_task):
        """测试git diff没有变化时不启动审查。"""
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        mock_create_task.reset_mock()
        
        self._setup_git_mocks(mock_exists, mock_run)  # 重新设置mock
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_not_called()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_change_ui_message(self, mock_exists, mock_run, mock_create_task):
        """测试没有变化时发送UI消息。"""
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        mock_create_task.reset_mock()
        
        self._setup_git_mocks(mock_exists, mock_run)  # 重新设置mock
        
        with patch.object(self.plugin.group_chat, 'send_if_exists') as mock_send:
            asyncio.run(self.plugin.before_waiting_user(self.agent))
            mock_create_task.assert_not_called()
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            self.assertEqual(call_args[0][0], "ui_log")
            self.assertEqual(call_args[0][1].content, "未触发SubAgent审核：检测到与上一次完全相同的git更改，无需重复审查")

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_with_deleted_files(self, mock_exists, mock_run, mock_create_task):
        """测试有删除文件时启动审查。"""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(stdout="diff --git a/test.py b/test.py\n+print('hello')", returncode=0),
            Mock(stdout="", returncode=0),
            Mock(stdout=" D deleted_file.py", returncode=0)
        ]
        
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()
        self.assertEqual(mock_run.call_count, 3)
        mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_with_staged_deleted_files(self, mock_exists, mock_run, mock_create_task):
        """测试有暂存区删除文件时启动审查。"""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(stdout="diff --git a/test.py b/test.py\n+print('hello')", returncode=0),
            Mock(stdout="", returncode=0),
            Mock(stdout="D  staged_deleted_file.py", returncode=0)
        ]
        
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()
        self.assertEqual(mock_run.call_count, 3)
        mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_git_diff_changed(self, mock_exists, mock_run, mock_create_task):
        """测试git diff变化时重新启动审查。"""
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        mock_create_task.reset_mock()
        
        changed_git_diff = "diff --git a/test.py b/test.py\n+print('changed')"
        self._setup_git_mocks(mock_exists, mock_run, git_diff=changed_git_diff)
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_new_files_changed(self, mock_exists, mock_run, mock_create_task):
        """测试新增文件内容变化时重新启动审查。"""
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        mock_create_task.reset_mock()
        
        self._setup_git_mocks(mock_exists, mock_run)
        with patch.object(self.plugin, '_get_new_files_content') as mock_new_files:
            mock_new_files.return_value = "**新增文件: new_file.py**\n```\nchanged content\n```"
            asyncio.run(self.plugin.before_waiting_user(self.agent))
            mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_deleted_files_changed(self, mock_exists, mock_run, mock_create_task):
        """测试删除文件列表变化时重新启动审查。"""
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        mock_create_task.reset_mock()
        
        changed_status = " D deleted_file.py\n D another_deleted_file.py"
        self._setup_git_mocks(mock_exists, mock_run, ls_files_output=changed_status)
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()

    def test_register(self):
        """测试插件注册。"""
        lifecycle = Mock()
        lifecycle.register_after_message_generation = Mock()
        lifecycle.register_before_waiting_user = Mock()
        
        self.plugin.register(lifecycle)
        
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )
        lifecycle.register_before_waiting_user.assert_called_once_with(
            self.plugin.before_waiting_user
        )

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_get_new_files_content_with_folder(self, mock_exists, mock_run):
        """测试_get_new_files_content方法处理新增文件夹。"""
        mock_exists.return_value = True
        
        mock_run.return_value = Mock(
            stdout="new_file.py\nfolder/another_file.py\nsubdir/test.txt\n",
            returncode=0
        )
        
        with patch("builtins.open", mock_open(read_data="file content")):
            result = self.plugin._get_new_files_content()
            
            mock_run.assert_called_once_with(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                check=True
            )
            
            self.assertIsInstance(result, str)
            result_str = cast(str, result)  # 使用cast明确类型
            self.assertIn("**新增文件: new_file.py**", result_str)
            self.assertIn("**新增文件: folder/another_file.py**", result_str)
            self.assertIn("**新增文件: subdir/test.txt**", result_str)
            self.assertIn("file content", result_str)

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_get_new_files_content_respects_gitignore(self, mock_exists, mock_run):
        """测试_get_new_files_content方法尊重.gitignore。"""
        mock_exists.return_value = True
        
        mock_run.return_value = Mock(stdout="", returncode=0)
        
        result = self.plugin._get_new_files_content()
        
        mock_run.assert_called_once_with(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True
        )
        
        self.assertIsInstance(result, str)
        result_str = cast(str, result)  # 使用cast明确类型
        self.assertEqual(result_str, "")

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_get_new_files_content_with_unreadable_files(self, mock_exists, mock_run):
        """测试_get_new_files_content方法处理无法读取的文件。"""
        mock_exists.return_value = True
        
        mock_run.return_value = Mock(stdout="unreadable_file.bin\n", returncode=0)
        
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = self.plugin._get_new_files_content()
            
            self.assertIsInstance(result, str)
            result_str = cast(str, result)  # 使用cast明确类型
            self.assertIn("**新增文件: unreadable_file.bin**", result_str)
            self.assertIn("(无法读取文件内容)", result_str)

    def test_after_message_generation_records_tool_use(self):
        """测试after_message_generation方法记录工具使用。"""
        self.plugin._agent_used_file_modification_tools = False
        
        mock_answer = Mock()
        tool_calls = [{"name": "write_file", "arguments": {"filepath": "test.py", "content": "print('hello')", "override": True}}]
        asyncio.run(self.plugin.after_message_generation(mock_answer, "", tool_calls))
        
        self.assertTrue(self.plugin._agent_used_file_modification_tools)

    def test_after_message_generation_ignores_non_file_tools(self):
        """测试after_message_generation方法忽略非文件修改工具。"""
        self.plugin._agent_used_file_modification_tools = False
        
        mock_answer = Mock()
        tool_calls = [{"name": "run_command", "arguments": {"command": "ls -la"}}]
        asyncio.run(self.plugin.after_message_generation(mock_answer, "", tool_calls))
        
        self.assertFalse(self.plugin._agent_used_file_modification_tools)

    def test_before_waiting_user_without_tool_use(self):
        """测试Agent没有使用文件修改工具时不启动审查。"""
        self.plugin._agent_used_file_modification_tools = False
        
        self._setup_subagent_manager()
        
        with patch.object(self.plugin, '_get_git_diff') as mock_git_diff:
            mock_git_diff.return_value = "diff --git a/test.py b/test.py\n+print('hello')"
            
            with patch.object(self.plugin.group_chat, 'send_if_exists') as mock_send:
                asyncio.run(self.plugin.before_waiting_user(self.agent))
                
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                self.assertEqual(call_args[0][0], "ui_log")



    @patch("os.path.getsize")
    @patch("builtins.open")
    @patch("os.path.isdir")
    def test_read_single_file_content_large_file(self, mock_isdir, mock_open, mock_getsize):
        """测试_read_single_file_content方法处理大文件。"""
        mock_isdir.return_value = False
        
        mock_getsize.return_value = 33 * 1024  # 33KB
        
        result = self.plugin._read_single_file_content("large_file.txt")
        
        self.assertIsNotNone(result)
        from typing import cast
        result_str = cast(str, result)
        self.assertIn("**新增文件: large_file.txt**", result_str)
        self.assertIn("文件大小为", result_str)
        self.assertIn("大于32KB", result_str)
        self.assertNotIn("```", result_str)  # 不应该有代码块
        
        mock_getsize.assert_called_once_with("large_file.txt")
        mock_open.assert_not_called()
    
    @patch("os.path.getsize")
    @patch("builtins.open", mock_open(read_data="small content"))
    @patch("os.path.isdir")
    def test_read_single_file_content_small_file(self, mock_isdir, mock_getsize):
        """测试_read_single_file_content方法处理小文件。"""
        mock_isdir.return_value = False
        
        mock_getsize.return_value = 30 * 1024  # 30KB
        
        result = self.plugin._read_single_file_content("small_file.txt")
        
        self.assertIsNotNone(result)
        from typing import cast
        result_str = cast(str, result)
        self.assertIn("**新增文件: small_file.txt**", result_str)
        self.assertIn("small content", result_str)
        self.assertIn("```", result_str)  # 应该有代码块
        
        mock_getsize.assert_called_once_with("small_file.txt")
    
    @patch("os.path.getsize")
    @patch("os.path.isdir")
    def test_read_single_file_content_getsize_fails(self, mock_isdir, mock_getsize):
        """测试_read_single_file_content方法在获取文件大小失败时尝试读取内容。"""
        mock_isdir.return_value = False
        
        mock_getsize.side_effect = OSError("Permission denied")
        
        with patch("builtins.open", mock_open(read_data="test content")) as mock_file:
            result = self.plugin._read_single_file_content("test_file.txt")
            
            self.assertIsNotNone(result)
            from typing import cast
            result_str = cast(str, result)
            self.assertIn("**新增文件: test_file.txt**", result_str)
            self.assertIn("test content", result_str)
            
            mock_getsize.assert_called_once_with("test_file.txt")
            mock_file.assert_called_once_with("test_file.txt", "r", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()

    def tearDown(self):
        """清理测试环境。"""
        import os
        if hasattr(self, 'temp_code_style_file'):
            try:
                os.unlink(self.temp_code_style_file.name)
            except (OSError, FileNotFoundError):
                pass