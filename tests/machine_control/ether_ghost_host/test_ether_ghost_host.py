"""Tests for EtherGhostMachineControl."""

import unittest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from linhai.machine_control.ether_ghost_host.ether_ghost_host import (
    EtherGhostMachineControl,
)
from linhai.tool.base import ToolResultSuccess, ToolResultFailed
from linhai.agent.base import FileContentMessage


class TestEtherGhostMachineControl(unittest.IsolatedAsyncioTestCase):
    """Test cases for EtherGhostMachineControl."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_type = "php_oneliner"
        self.connection_args: Dict[str, Any] = {
            "url": "http://example.com/shell.php",
            "password": "pass123",
        }
        self.machine_id = "test_ether_ghost"

    @patch(
        "linhai.machine_control.ether_ghost_host.ether_ghost_host.session_type_info",
        {
            "php_oneliner": {
                "constructor": MagicMock(return_value=AsyncMock()),
            },
        },
    )
    async def test_initialize_success(self):
        """Test successful initialization of session."""
        mock_session = AsyncMock()
        mock_session.get_pwd = AsyncMock(return_value="/tmp")
        with patch(
            "linhai.machine_control.ether_ghost_host.ether_ghost_host.session_type_info",
            {"php_oneliner": {"constructor": MagicMock(return_value=mock_session)}},
        ):
            control = EtherGhostMachineControl(
                session_type=self.session_type,
                connection_args=self.connection_args,
                machine_id=self.machine_id,
            )
            await control.initialize()
            self.assertIsNotNone(control.session)
            self.assertEqual(control.current_dir, "/tmp")

    async def test_initialize_unsupported_session_type(self):
        """Test initialization with unsupported session type."""
        with patch(
            "linhai.machine_control.ether_ghost_host.ether_ghost_host.session_type_info",
            {},
        ):
            control = EtherGhostMachineControl(
                session_type="invalid_type",
                connection_args=self.connection_args,
                machine_id=self.machine_id,
            )
            with self.assertRaises(RuntimeError) as cm:
                await control.initialize()
            self.assertIn("不支持的session类型", str(cm.exception))

    async def test_http_request_without_session(self):
        """Test http_request when session is not initialized."""
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        result = await control.http_request("GET", "http://example.com")
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("Session未初始化", result.content)

    async def test_read_file_without_session(self):
        """Test read_file when session is not initialized."""
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        result = await control.read_file("/tmp/test.txt")
        self.assertIsInstance(result, ToolResultFailed)
        self.assertIn("Session未初始化", result.content)

    async def test_read_file_with_line_numbers(self):
        """Test read_file with show_line_numbers=True."""
        mock_session = AsyncMock()
        # 模拟一个三行的文件
        mock_session.get_file_contents = AsyncMock(return_value=b"line1\nline2\nline3")
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        control.session = mock_session
        result = await control.read_file("/tmp/test.txt", show_line_numbers=True)
        # 检查行号格式
        self.assertIn("   1: line1", result.content)
        self.assertIn("   2: line2", result.content)
        self.assertIn("   3: line3", result.content)

    async def test_list_files_without_session(self):
        """Test list_files when session is not initialized."""
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        result = await control.list_files("/tmp")
        self.assertIn("Session未初始化", result.content)

    async def test_http_request_returns_headers(self):
        """Test http_request returns <<>> format with headers."""
        mock_session = AsyncMock()
        # 模拟一个包含headers的HTTP响应
        mock_session.send_http_request = AsyncMock(
            return_value={
                "status_code": 200,
                "headers": {"Content-Type": "application/json", "Server": "nginx"},
                "body": b'{"test": "data"}',
            }
        )
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        control.session = mock_session
        result = await control.http_request("GET", "http://example.com")
        # 检查返回的是ToolResultSuccess，内容为<<>>格式
        content = result.content
        self.assertIn("<<status_code>>", content)
        self.assertIn("<<headers>>", content)
        self.assertIn("<<body>>", content)
        # 解析<<>>格式
        lines = content.split("\n")
        status_line = [l for l in lines if l.startswith("<<status_code>>")][0]
        headers_line = [l for l in lines if l.startswith("<<headers>>")][0]
        body_line = [l for l in lines if l.startswith("<<body>>")][0]
        
        self.assertEqual(status_line, "<<status_code>>200<<status_code>>")
        self.assertIn("Content-Type: application/json", headers_line)
        self.assertIn("Server: nginx", headers_line)
        self.assertIn('{"test": "data"}', body_line)

    async def test_http_request_binary_content(self):
        """Test http_request with binary content returns file_path in <<>> format."""
        mock_session = AsyncMock()
        # 模拟一个二进制响应，无法UTF-8解码
        mock_session.send_http_request = AsyncMock(
            return_value={
                "status_code": 200,
                "headers": {"Content-Type": "application/octet-stream"},
                "body": b"\x89PNG\r\n\x1a\n",
            }
        )
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        control.session = mock_session
        result = await control.http_request("GET", "http://example.com/image.png")
        self.assertIsInstance(result, ToolResultSuccess)
        # 解析<<>>格式
        content = result.content
        self.assertIn("<<status_code>>", content)
        self.assertIn("<<headers>>", content)
        self.assertIn("<<file_path>>", content)
        
        lines = content.split("\n")
        status_line = [l for l in lines if l.startswith("<<status_code>>")][0]
        headers_line = [l for l in lines if l.startswith("<<headers>>")][0]
        file_path_line = [l for l in lines if l.startswith("<<file_path>>")][0]
        
        self.assertEqual(status_line, "<<status_code>>200<<status_code>>")
        self.assertIn("Content-Type: application/octet-stream", headers_line)
        # 提取文件路径
        file_path = file_path_line.replace("<<file_path>>", "").replace("<<file_path>>", "")
        # 清理临时文件
        import os
        if os.path.exists(file_path):
            os.unlink(file_path)

    async def test_list_files_success(self):
        """Test list_files with mock directory entries."""
        from ether_ghost.core.base import DirectoryEntry

        mock_session = AsyncMock()
        # 模拟两个条目：一个目录，一个文件，带权限和文件大小
        mock_session.list_dir = AsyncMock(
            return_value=[
                DirectoryEntry(
                    name="docs", permission="rwxr-xr-x", filesize=4096, entry_type="dir"
                ),
                DirectoryEntry(
                    name="readme.txt",
                    permission="rw-r--r--",
                    filesize=1024,
                    entry_type="file",
                ),
            ]
        )
        control = EtherGhostMachineControl(
            session_type=self.session_type,
            connection_args=self.connection_args,
            machine_id=self.machine_id,
        )
        control.session = mock_session
        result = await control.list_files("/tmp")
        # 检查输出包含目录和文件，以及正确的权限和文件大小格式
        self.assertIn("drwxr-xr-x     4096 docs", result.content)
        self.assertIn("-rw-r--r--     1024 readme.txt", result.content)

    # Add more tests for other methods as needed


if __name__ == "__main__":
    unittest.main()
