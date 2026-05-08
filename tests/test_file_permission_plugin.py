import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import tempfile
import shutil

from linhai.plugin import FileOperationPermissionPlugin
from linhai.registry import Registry
from linhai.tool.base import FailedToolResult
from linhai.config import ToolConfig, FileOperationRule


class TestFileOperationPermissionPlugin(unittest.IsolatedAsyncioTestCase):
    """测试文件操作权限插件"""

    def setUp(self):
        self.registry = MagicMock(spec=Registry)
        self.pwd = Path.cwd()
        self.temp_dir = tempfile.mkdtemp(dir=self.pwd)
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("测试内容\n第二行\n第三行", encoding="utf-8")
        self.tool_config = MagicMock(spec=ToolConfig)
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "ALLOW"
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )

    def tearDown(self):
        if hasattr(self, "temp_dir") and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_init(self):
        self.assertEqual(self.plugin.registry, self.registry)
        self.assertEqual(self.plugin.pwd, self.pwd)
        self.assertEqual(self.plugin.rules, self.tool_config.file_operation_rules)
        self.assertEqual(
            self.plugin.default_rule, self.tool_config.file_operation_default_rule
        )

    async def test_check_permission_allow_read(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = self.plugin.check_permission("read", str(self.test_file))
        self.assertTrue(result)

    async def test_check_permission_block_write(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = self.plugin.check_permission("write", str(self.test_file))
        self.assertFalse(result)

    async def test_check_permission_read_write_operation(self):
        rule = FileOperationRule(
            operation="READ_WRITE", pattern="**/*.txt", action="BLOCK"
        )
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        self.assertFalse(self.plugin.check_permission("read", str(self.test_file)))
        self.assertFalse(self.plugin.check_permission("write", str(self.test_file)))

    async def test_check_permission_with_relative_path(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        relative_path = self.test_file.relative_to(self.pwd)
        result = self.plugin.check_permission("read", str(relative_path))
        self.assertTrue(result)

    async def test_check_permission_default_rule_allow(self):
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "ALLOW"
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = self.plugin.check_permission("read", str(self.test_file))
        self.assertTrue(result)

    async def test_check_permission_default_rule_block(self):
        self.tool_config.file_operation_rules = []
        self.tool_config.file_operation_default_rule = "BLOCK"
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = self.plugin.check_permission("read", str(self.test_file))
        self.assertFalse(result)

    async def test_before_tool_call_read_file_allowed(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = await self.plugin.before_tool_call(
            tool_name="read_file",
            toolcall_arguments={"filepath": str(self.test_file)},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)

    async def test_before_tool_call_write_file_blocked(self):
        rule = FileOperationRule(operation="WRITE", pattern="**/*.txt", action="BLOCK")
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = await self.plugin.before_tool_call(
            tool_name="write_file",
            toolcall_arguments={
                "filepath": str(self.test_file),
                "content": "新内容",
                "override": True,
            },
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsInstance(result, FailedToolResult)
        self.assertIn("文件操作被阻止", result.content)

    async def test_before_tool_call_unsupported_tool(self):
        rule = FileOperationRule(operation="READ", pattern="**/*.txt", action="ALLOW")
        self.tool_config.file_operation_rules = [rule]
        self.plugin = FileOperationPermissionPlugin(
            self.registry, self.pwd, self.tool_config
        )
        result = await self.plugin.before_tool_call(
            tool_name="unsupported_tool",
            toolcall_arguments={},
            with_secret={"in_arguments": [], "in_result": []},
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
