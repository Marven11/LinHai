"""测试Git diff审查插件。"""

import unittest
from unittest.mock import Mock, patch
import asyncio

from linhai.subagent.plugin import GitDiffReviewPlugin
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
        
        # 设置通用的mock返回值
        self.mock_git_diff = "diff --git a/test.py b/test.py\n+print('hello')"
        self.mock_empty = ""
        self.mock_status_empty = ""
        self.mock_status_deleted = " D deleted_file.py"

    def _setup_subagent_manager(self):
        """设置SubAgentManager的mock。"""
        from linhai.subagent import SubAgentManager
        subagent_manager = Mock(spec=SubAgentManager)
        # 使用普通Mock而不是AsyncMock来避免警告
        subagent_manager.create_subagent = Mock(return_value="success")
        self.group_chat.register_member("subagent_manager", subagent_manager)
        return subagent_manager

    def _setup_git_mocks(self, mock_exists, mock_run, git_diff=None, status_output=None):
        """设置git相关命令的mock。"""
        mock_exists.return_value = True
        
        # 默认的mock返回值
        if git_diff is None:
            git_diff = self.mock_git_diff
        if status_output is None:
            status_output = self.mock_status_empty
            
        mock_run.side_effect = [
            Mock(stdout=git_diff, returncode=0),      # git diff --cached
            Mock(stdout=self.mock_empty, returncode=0), # git diff
            Mock(stdout=status_output, returncode=0)   # git status --porcelain
        ]

    def test_plugin_initialization(self):
        """测试插件初始化。"""
        self.assertIsInstance(self.plugin, GitDiffReviewPlugin)
        self.assertEqual(self.plugin.group_chat, self.group_chat)

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_git_repo(self, mock_exists, mock_run):
        """测试不在git仓库时不启动审查。"""
        mock_exists.return_value = False
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()  # 会被调用3次：.git, TODO.md, LINHAI.md
        mock_run.assert_not_called()

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_before_waiting_user_no_diff(self, mock_exists, mock_run):
        """测试没有git diff时不启动审查。"""
        mock_exists.return_value = True
        mock_run.return_value = Mock(stdout="", returncode=0)
        
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
        
        from linhai.subagent import SubAgentManager
        subagent_manager = Mock(spec=SubAgentManager)
        # 使用普通Mock而不是AsyncMock来避免警告
        subagent_manager.create_subagent = Mock(return_value="success")
        self.group_chat.register_member("subagent_manager", subagent_manager)
        
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
        
        from linhai.subagent import SubAgentManager
        subagent_manager = Mock(spec=SubAgentManager)
        # 使用普通Mock而不是AsyncMock来避免警告
        subagent_manager.create_subagent = Mock(return_value="success")
        self.group_chat.register_member("subagent_manager", subagent_manager)
        
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
        
        from linhai.subagent import SubAgentManager
        subagent_manager = Mock(spec=SubAgentManager)
        # 使用普通Mock而不是AsyncMock来避免警告
        subagent_manager.create_subagent = Mock(return_value="success")
        self.group_chat.register_member("subagent_manager", subagent_manager)
        
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
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()
        
        # 重置mock
        mock_create_task.reset_mock()
        
        # 第二次调用：删除文件列表变化，应该重新启动审查
        changed_status = " D deleted_file.py\n D another_deleted_file.py"
        self._setup_git_mocks(mock_exists, mock_run, status_output=changed_status)
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        mock_create_task.assert_called_once()

    def test_register(self):
        """测试插件注册。"""
        lifecycle = Mock()
        lifecycle.register_before_waiting_user = Mock()
        
        self.plugin.register(lifecycle)
        
        lifecycle.register_before_waiting_user.assert_called_once_with(
            self.plugin.before_waiting_user
        )


if __name__ == "__main__":
    unittest.main()
