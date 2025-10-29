"""Unit tests for modify_file_with_sed tool with line number warning."""

import unittest
import unittest.mock

from linhai.tool.base import ToolArgInfo
class TestModifyFileWithSedLineNumberWarning(unittest.TestCase):
    """Test cases for modify_file_with_sed tool with line number warning."""

    def setUp(self):
        # 为每个测试创建新的ToolSet实例
        from linhai.tool.base import ToolSet

        self.toolset = ToolSet()
        # 注册modify_file_with_sed工具
        from linhai.tool.tools.file import modify_file_with_sed

        self.toolset.register_tool(
            name="modify_file_with_sed",
            desc="使用sed表达式修改文件",
            args={
                "filepath": ToolArgInfo(desc="文件路径", type="str"),
                "expression": ToolArgInfo(desc="sed表达式", type="str"),
            },
            required_args=["filepath", "expression"],
        )(modify_file_with_sed)

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    @unittest.mock.patch("linhai.tool.tools.file.platform.system")
    @unittest.mock.patch("linhai.tool.tools.file.subprocess.run")
    def test_modify_file_with_sed_line_number_warning(
        self, mock_run, mock_system, mock_path
    ):
        """测试使用行号表达式时返回警告"""
        # 模拟macOS系统
        mock_system.return_value = "Darwin"

        # 模拟文件存在且是文件
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        # 模拟sed命令成功执行
        mock_run.return_value.returncode = 0

        # 使用行号表达式（以数字开头）
        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {"filepath": "test.txt", "expression": "1s/old/new/"},
        )

        # 验证返回结果包含警告
        self.assertIn("警告：使用行号匹配并修改文件", result)
        self.assertIn("文件的行号已经变化", result)
        self.assertIn("使用行号匹配是不推荐的行为", result)

        # 验证sed命令被正确调用
        mock_run.assert_called_once_with(
            ["sed", "-i", "", "1s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    @unittest.mock.patch("linhai.tool.tools.file.platform.system")
    @unittest.mock.patch("linhai.tool.tools.file.subprocess.run")
    def test_modify_file_with_sed_no_line_number_warning(
        self, mock_run, mock_system, mock_path
    ):
        """测试使用非行号表达式时不返回警告"""
        # 模拟macOS系统
        mock_system.return_value = "Darwin"

        # 模拟文件存在且是文件
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        # 模拟sed命令成功执行
        mock_run.return_value.returncode = 0

        # 使用非行号表达式（不以数字开头）
        result = self.toolset.call_tool(
            "modify_file_with_sed", {"filepath": "test.txt", "expression": "s/old/new/"}
        )

        # 验证返回结果不包含警告
        self.assertNotIn("警告：使用行号匹配并修改文件", result)
        self.assertIn("已使用sed表达式修改", result)

        # 验证sed命令被正确调用
        mock_run.assert_called_once_with(
            ["sed", "-i", "", "s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    @unittest.mock.patch("linhai.tool.tools.file.platform.system")
    @unittest.mock.patch("linhai.tool.tools.file.subprocess.run")
    def test_modify_file_with_sed_line_range_warning(
        self, mock_run, mock_system, mock_path
    ):
        """测试使用行号范围表达式时返回警告"""
        # 模拟macOS系统
        mock_system.return_value = "Darwin"

        # 模拟文件存在且是文件
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        # 模拟sed命令成功执行
        mock_run.return_value.returncode = 0

        # 使用行号范围表达式（以数字开头）
        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {"filepath": "test.txt", "expression": "1,5s/old/new/"},
        )

        # 验证返回结果包含警告
        self.assertIn("警告：使用行号匹配并修改文件", result)
        self.assertIn("文件的行号已经变化", result)
        self.assertIn("使用行号匹配是不推荐的行为", result)

        # 验证sed命令被正确调用
        mock_run.assert_called_once_with(
            ["sed", "-i", "", "1,5s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
        )

    @unittest.mock.patch("linhai.tool.tools.file.Path")
    @unittest.mock.patch("linhai.tool.tools.file.platform.system")
    @unittest.mock.patch("linhai.tool.tools.file.subprocess.run")
    def test_modify_file_with_sed_linux_system(self, mock_run, mock_system, mock_path):
        """测试在Linux系统上的行为"""
        # 模拟Linux系统
        mock_system.return_value = "Linux"

        # 模拟文件存在且是文件
        mock_file = mock_path.return_value
        mock_file.exists.return_value = True
        mock_file.is_file.return_value = True
        mock_file.as_posix.return_value = "test.txt"

        # 模拟sed命令成功执行
        mock_run.return_value.returncode = 0

        # 使用行号表达式
        result = self.toolset.call_tool(
            "modify_file_with_sed",
            {"filepath": "test.txt", "expression": "1s/old/new/"},
        )

        # 验证返回结果包含警告
        self.assertIn("警告：使用行号匹配并修改文件", result)

        # 验证sed命令在Linux系统上被正确调用
        mock_run.assert_called_once_with(
            ["sed", "-i", "1s/old/new/", "test.txt"],
            capture_output=True,
            text=True,
            check=True,
