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
        
        # 设置通用的mock返回值
        self.mock_git_diff = "diff --git a/test.py b/test.py\n+print('hello')"
        self.mock_empty = ""
        self.mock_status_empty = ""
        self.mock_status_deleted = " D deleted_file.py"
        
        # 默认设置subagent_manager，避免测试环境出错
        from linhai.subagent import SubAgentManager
        self.subagent_manager = Mock(spec=SubAgentManager)
        self.subagent_manager.subagent_config = None  # 默认不启用
        self.group_chat.register_member("subagent_manager", self.subagent_manager)

    def _setup_subagent_manager(self):
        """设置SubAgentManager的mock。"""
        from linhai.subagent import SubAgentManager
        from linhai.config import SubAgentConfig
        try:
            subagent_manager = self.group_chat.get_members("subagent_manager", SubAgentManager)
        except RuntimeError:
            subagent_manager = Mock(spec=SubAgentManager)
            self.group_chat.register_member("subagent_manager", subagent_manager)
        # 设置一个启用的subagent_config
        subagent_config = Mock(spec=SubAgentConfig)
        subagent_config.enable = True
        subagent_config.enabled_agent_types = {"git_diff_reviewer": True}  # 启用git_diff_reviewer
        subagent_manager.subagent_config = subagent_config
        # 使用普通Mock而不是AsyncMock来避免警告
        subagent_manager.create_subagent = Mock(return_value="success")
        return subagent_manager

    def _setup_for_review(self):
        """设置审查条件：Agent使用了文件修改工具。"""
        self.plugin._agent_used_file_modification_tools = True

    def _setup_git_mocks(self, mock_exists, mock_run, git_diff=None, ls_files_output=None):
        """设置git相关命令的mock。"""
        mock_exists.return_value = True
        
        # 默认的mock返回值
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
        # 第一次调用：会启动审查
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        # 重置mock
        mock_create_task.reset_mock()
        
        # 第二次调用相同内容，不应该启动审查
        self._setup_git_mocks(mock_exists, mock_run)  # 重新设置mock
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_not_called()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_change_ui_message(self, mock_exists, mock_run, mock_create_task):
        """测试没有变化时发送UI消息。"""
        # 第一次调用：会启动审查
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        # 重置mock
        mock_create_task.reset_mock()
        
        # 第二次调用相同内容，不应该启动审查但应该发送UI消息
        self._setup_git_mocks(mock_exists, mock_run)  # 重新设置mock
        
        # 模拟UI消息发送
        with patch.object(self.plugin.group_chat, 'send_if_exists') as mock_send:
            asyncio.run(self.plugin.before_waiting_user(self.agent))
            mock_create_task.assert_not_called()
            # 验证UI消息被发送
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
        # 第一次调用：设置初始缓存
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        # 重置mock
        mock_create_task.reset_mock()
        
        # 第二次调用：git diff变化，应该重新启动审查
        changed_git_diff = "diff --git a/test.py b/test.py\n+print('changed')"
        self._setup_git_mocks(mock_exists, mock_run, git_diff=changed_git_diff)
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_new_files_changed(self, mock_exists, mock_run, mock_create_task):
        """测试新增文件内容变化时重新启动审查。"""
        # 第一次调用：设置初始缓存
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        # 重置mock
        mock_create_task.reset_mock()
        
        # 第二次调用：新增文件内容变化，应该重新启动审查
        # 重新设置git mock
        self._setup_git_mocks(mock_exists, mock_run)
        # 模拟有新增文件的情况
        with patch.object(self.plugin, '_get_new_files_content') as mock_new_files:
            mock_new_files.return_value = "**新增文件: new_file.py**\n```\nchanged content\n```"
            asyncio.run(self.plugin.before_waiting_user(self.agent))
            mock_create_task.assert_called_once()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_deleted_files_changed(self, mock_exists, mock_run, mock_create_task):
        """测试删除文件列表变化时重新启动审查。"""
        # 第一次调用：设置初始缓存
        self._setup_git_mocks(mock_exists, mock_run)
        self._setup_subagent_manager()
        self._setup_for_review()
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        # 重置mock
        mock_create_task.reset_mock()
        
        # 第二次调用：删除文件列表变化，应该重新启动审查
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
        
        # 模拟git ls-files返回多个文件（包括文件夹中的文件）
        mock_run.return_value = Mock(
            stdout="new_file.py\nfolder/another_file.py\nsubdir/test.txt\n",
            returncode=0
        )
        
        # 模拟文件读取
        with patch("builtins.open", mock_open(read_data="file content")):
            result = self.plugin._get_new_files_content()
            
            # 验证调用了git ls-files命令
            mock_run.assert_called_once_with(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # 验证结果包含所有文件
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
        
        # 模拟git ls-files返回空（所有文件都被.gitignore忽略）
        mock_run.return_value = Mock(stdout="", returncode=0)
        
        result = self.plugin._get_new_files_content()
        
        # 验证调用了git ls-files命令
        mock_run.assert_called_once_with(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 验证返回空字符串
        self.assertIsInstance(result, str)
        result_str = cast(str, result)  # 使用cast明确类型
        self.assertEqual(result_str, "")

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_get_new_files_content_with_unreadable_files(self, mock_exists, mock_run):
        """测试_get_new_files_content方法处理无法读取的文件。"""
        mock_exists.return_value = True
        
        # 模拟git ls-files返回文件
        mock_run.return_value = Mock(stdout="unreadable_file.bin\n", returncode=0)
        
        # 模拟文件读取失败
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            result = self.plugin._get_new_files_content()
            
            # 验证结果包含无法读取的提示
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
        # 设置Agent没有使用文件修改工具
        self.plugin._agent_used_file_modification_tools = False
        
        self._setup_subagent_manager()
        
        # 模拟有git diff
        with patch.object(self.plugin, '_get_git_diff') as mock_git_diff:
            mock_git_diff.return_value = "diff --git a/test.py b/test.py\n+print('hello')"
            
            # 模拟UI消息发送
            with patch.object(self.plugin.group_chat, 'send_if_exists') as mock_send:
                asyncio.run(self.plugin.before_waiting_user(self.agent))
                
                # 验证发送了未触发审查的UI消息
                mock_send.assert_called_once()
                call_args = mock_send.call_args
                self.assertEqual(call_args[0][0], "ui_log")
                self.assertEqual(call_args[0][1].content, "未触发SubAgent审核：Agent没有使用文件修改工具")

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_subagent_manager(self, mock_exists, mock_run, mock_create_task):
        """测试subagent_manager不存在时抛出RuntimeError。"""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(stdout="diff --git a/test.py b/test.py\n+print('hello')", returncode=0),
            Mock(stdout="", returncode=0),
            Mock(stdout="", returncode=0)
        ]
        
        # 创建一个新的GroupChat实例，其中没有注册subagent_manager
        from linhai.group_chat import GroupChat
        new_group_chat = GroupChat()
        self.plugin.group_chat = new_group_chat
        
        self._setup_for_review()
        
        # 应该抛出RuntimeError
        with self.assertRaises(RuntimeError):
            asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        # 验证没有启动审查任务
        mock_create_task.assert_not_called()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_subagent_config(self, mock_exists, mock_run, mock_create_task):
        """测试subagent_manager存在但subagent_config为None时抛出AttributeError。"""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(stdout="diff --git a/test.py b/test.py\n+print('hello')", returncode=0),
            Mock(stdout="", returncode=0),
            Mock(stdout="", returncode=0)
        ]
        
        # 使用setUp中已注册的subagent_manager，但设置subagent_config为None
        self.subagent_manager.subagent_config = None  # 关键：配置为None
        
        self._setup_for_review()
        
        # 应该抛出AttributeError
        with self.assertRaises(AttributeError):
            asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        # 验证没有启动审查任务
        mock_create_task.assert_not_called()

    @patch("asyncio.create_task")
    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_subagent_disabled(self, mock_exists, mock_run, mock_create_task):
        """测试subagent配置禁用时不启动审查。"""
        mock_exists.return_value = True
        mock_run.side_effect = [
            Mock(stdout="diff --git a/test.py b/test.py\n+print('hello')", returncode=0),
            Mock(stdout="", returncode=0),
            Mock(stdout="", returncode=0)
        ]
        
        # 使用setUp中已注册的subagent_manager，设置配置启用但git_diff_reviewer类型禁用
        from linhai.config import SubAgentConfig
        
        subagent_config = Mock(spec=SubAgentConfig)
        subagent_config.enable = True
        subagent_config.enabled_agent_types = {"git_diff_reviewer": False}  # git_diff_reviewer禁用
        self.subagent_manager.subagent_config = subagent_config
        
        self._setup_for_review()
        
        # 应该正常执行而不启动审查
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        # 验证没有启动审查任务
        mock_create_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()