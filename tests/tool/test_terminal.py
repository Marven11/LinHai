"""终端工具测试模块"""

import unittest
import asyncio
from linhai.machine_control.master_host import terminal_toolset


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
            "terminal_create",
            "terminal_send_keys",
            "terminal_send_string",
            "terminal_read_screen",
            "terminal_close",
        }
        self.assertEqual(tool_names, expected_tools)

    def test_create_terminal(self):
        """测试创建终端"""

        async def test():
            create_func = terminal_toolset.get_tool("terminal_create")
            result = await create_func()
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)  # 应该返回有效的id

        self.loop.run_until_complete(test())

    def test_send_string_and_read_screen(self):
        """测试发送字符串和读取屏幕"""

        async def test():
            create_func = terminal_toolset.get_tool("terminal_create")
            terminal_id = await create_func()

            send_string_func = terminal_toolset.get_tool("terminal_send_string")
            result = await send_string_func(terminal_id, "echo hello", with_enter=True)
            self.assertIn("已发送", result)

            read_func = terminal_toolset.get_tool("terminal_read_screen")
            screen_content = await read_func(terminal_id)
            self.assertIsInstance(screen_content, str)

            close_func = terminal_toolset.get_tool("terminal_close")
            close_result = await close_func(terminal_id)
            self.assertIn("已关闭终端", close_result)

        self.loop.run_until_complete(test())

    def test_send_string_without_enter(self):
        """测试发送字符串但不发送enter键"""

        async def test():
            create_func = terminal_toolset.get_tool("terminal_create")
            terminal_id = await create_func()

            send_string_func = terminal_toolset.get_tool("terminal_send_string")
            result = await send_string_func(terminal_id, "echo hello", with_enter=False)
            self.assertIn("已发送", result)

            close_func = terminal_toolset.get_tool("terminal_close")
            await close_func(terminal_id)

        self.loop.run_until_complete(test())

    def test_send_keys(self):
        """测试发送按键"""

        async def test():
            create_func = terminal_toolset.get_tool("terminal_create")
            terminal_id = await create_func()

            send_keys_func = terminal_toolset.get_tool("terminal_send_keys")
            result = await send_keys_func(
                terminal_id,
                ["e", "c", "h", "o", "space", "t", "e", "s", "t", "enter"],
            )
            self.assertIn("已发送按键", result)

            close_func = terminal_toolset.get_tool("terminal_close")
            await close_func(terminal_id)

        self.loop.run_until_complete(test())

    def test_send_special_keys(self):
        """测试发送特殊按键"""

        async def test():
            create_func = terminal_toolset.get_tool("terminal_create")
            terminal_id = await create_func()

            send_keys_func = terminal_toolset.get_tool("terminal_send_keys")
            result = await send_keys_func(
                terminal_id,
                ["up", "down", "left", "right", "tab", "pageup", "pagedown"],
            )
            self.assertIn("已发送按键", result)

            close_func = terminal_toolset.get_tool("terminal_close")
            await close_func(terminal_id)

        self.loop.run_until_complete(test())

    def test_invalid_terminal_id(self):
        """测试无效终端id"""

        async def test():
            read_func = terminal_toolset.get_tool("terminal_read_screen")
            result = await read_func("invalid-id")
            self.assertIn("错误：未找到终端", result)

            send_string_func = terminal_toolset.get_tool("terminal_send_string")
            result = await send_string_func("invalid-id", "ls", with_enter=True)
            self.assertIn("错误：未找到终端", result)

            send_keys_func = terminal_toolset.get_tool("terminal_send_keys")
            result = await send_keys_func("invalid-id", ["a"])
            self.assertIn("错误：未找到终端", result)

            close_func = terminal_toolset.get_tool("terminal_close")
            result = await close_func("invalid-id")
            self.assertIn("错误：未找到终端", result)

        self.loop.run_until_complete(test())

    def test_invalid_keys(self):
        """测试无效按键"""

        async def test():
            create_func = terminal_toolset.get_tool("terminal_create")
            terminal_id = await create_func()

            send_keys_func = terminal_toolset.get_tool("terminal_send_keys")
            result = await send_keys_func(terminal_id, ["invalid_key"])
            self.assertIn("未知按键", result)

            close_func = terminal_toolset.get_tool("terminal_close")
            await close_func(terminal_id)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
