"""测试Git diff审查插件。"""

import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import os
import tempfile
import subprocess

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
            Mock(stdout="", returncode=0)
        ]
        
        from linhai.subagent import SubAgentManager
        subagent_manager = Mock(spec=SubAgentManager)
        subagent_manager.create_subagent = AsyncMock(return_value="success")
        self.group_chat.register_member("subagent_manager", subagent_manager)
        
        asyncio.run(self.plugin.before_waiting_user(self.agent))
        
        mock_exists.assert_called()  # 会被调用3次：.git, TODO.md, LINHAI.md
        self.assertEqual(mock_run.call_count, 2)
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
