"""终端工具测试模块"""

import unittest
import asyncio
from linhai.tool.tools.terminal import terminal_toolset


class TestTerminalTools(unittest.TestCase):
    """终端工具测试类"""

    def setUp(self):
        """测试前准备"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """测试后清理"""
        self.loop.close()

    def test_toolset_has_correct_tools(self):
        """测试工具集包含正确的工具"""
        tools = terminal_toolset.get_tools()
        tool_names = set(tools.keys())
        expected_tools = {
            "create_terminal",
            "send_keys_to_terminal",
            "send_command_to_terminal",
            "read_terminal_screen",
            "close_terminal",
        }
        self.assertEqual(tool_names, expected_tools)

    def test_create_terminal(self):
        """测试创建终端"""

        async def test():
            create_func = terminal_toolset.get_tool("create_terminal")
            result = await create_func()
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)  # 应该返回有效的uuid

        self.loop.run_until_complete(test())

    def test_send_command_and_read_screen(self):
        """测试发送命令和读取屏幕"""

        async def test():
            # 创建终端
            create_func = terminal_toolset.get_tool("create_terminal")
            terminal_uuid = await create_func()

            # 发送命令
            send_cmd_func = terminal_toolset.get_tool("send_command_to_terminal")
            result = await send_cmd_func(terminal_uuid, "echo hello")
            self.assertIn("已发送命令", result)

            # 读取屏幕
            read_func = terminal_toolset.get_tool("read_terminal_screen")
            screen_content = await read_func(terminal_uuid)
            self.assertIsInstance(screen_content, str)

            # 关闭终端
            close_func = terminal_toolset.get_tool("close_terminal")
            close_result = await close_func(terminal_uuid)
            self.assertIn("已关闭终端", close_result)

        self.loop.run_until_complete(test())

    def test_send_keys(self):
        """测试发送按键"""

        async def test():
            # 创建终端
            create_func = terminal_toolset.get_tool("create_terminal")
            terminal_uuid = await create_func()

            # 发送按键
            send_keys_func = terminal_toolset.get_tool("send_keys_to_terminal")
            result = await send_keys_func(
                terminal_uuid,
                ["e", "c", "h", "o", "space", "t", "e", "s", "t", "enter"],
            )
            self.assertIn("已发送按键", result)

            # 关闭终端
            close_func = terminal_toolset.get_tool("close_terminal")
            await close_func(terminal_uuid)

        self.loop.run_until_complete(test())

    def test_invalid_terminal_uuid(self):
        """测试无效终端uuid"""

        async def test():
            # 测试读取不存在的终端
            read_func = terminal_toolset.get_tool("read_terminal_screen")
            result = await read_func("invalid-uuid")
            self.assertIn("错误：未找到终端", result)

            # 测试发送命令到不存在的终端
            send_cmd_func = terminal_toolset.get_tool("send_command_to_terminal")
            result = await send_cmd_func("invalid-uuid", "ls")
            self.assertIn("错误：未找到终端", result)

            # 测试关闭不存在的终端
            close_func = terminal_toolset.get_tool("close_terminal")
            result = await close_func("invalid-uuid")
            self.assertIn("错误：未找到终端", result)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
