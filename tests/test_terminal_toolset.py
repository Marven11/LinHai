"""测试终端工具集的功能，模拟agent环境"""

import unittest
import asyncio
from linhai.machine_control.master_host import (
    terminal_toolset,
    terminals,
    close_all_terminals,
)


class TestTerminalToolset(unittest.TestCase):
    """测试终端工具集"""

    def setUp(self):
        """设置测试环境"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        """清理测试环境"""
        self.loop.run_until_complete(asyncio.to_thread(close_all_terminals))
        self.loop.close()

    def test_terminal_lifecycle(self):
        """测试终端的完整生命周期"""
        tools = terminal_toolset.get_tools()
        create_terminal = tools["terminal_create"]["func"]
        self.assertIsNotNone(create_terminal, "create_terminal工具未找到")

        term_id = self.loop.run_until_complete(create_terminal(columns=80, lines=24))
        self.assertIsNotNone(term_id)
        self.assertIn(term_id, terminals)

        send_string = tools["terminal_send_string"]["func"]
        self.assertIsNotNone(send_string, "send_string_to_terminal工具未找到")

        result = self.loop.run_until_complete(
            send_string(term_id, "echo '114514'", with_enter=True)
        )
        self.assertIn("114514", result)

        read_screen = tools["terminal_read_screen"]["func"]
        self.assertIsNotNone(read_screen, "read_terminal_screen工具未找到")

        screen_content = self.loop.run_until_complete(read_screen(term_id))
        self.assertIn("114514", screen_content)

        send_keys = tools["terminal_send_keys"]["func"]
        self.assertIsNotNone(send_keys, "send_keys_to_terminal工具未找到")

        result = self.loop.run_until_complete(send_keys(term_id, ["ctrl+l"]))
        self.assertIn("已发送按键", result)

        close_terminal = tools["terminal_close"]["func"]
        self.assertIsNotNone(close_terminal, "close_terminal工具未找到")

        result = self.loop.run_until_complete(close_terminal(term_id))
        self.assertIn("已关闭终端", result)
        self.assertNotIn(term_id, terminals)

    def test_multiple_terminals(self):
        """测试多个终端同时运行"""
        tools = terminal_toolset.get_tools()
        create_terminal = tools["terminal_create"]["func"]
        send_string = tools["terminal_send_string"]["func"]
        read_screen = tools["terminal_read_screen"]["func"]
        close_terminal = tools["terminal_close"]["func"]

        term1 = self.loop.run_until_complete(create_terminal())
        term2 = self.loop.run_until_complete(create_terminal())

        self.loop.run_until_complete(
            send_string(term1, "echo '李田所'", with_enter=True)
        )
        self.loop.run_until_complete(
            send_string(term2, "echo '人类有三大欲望'", with_enter=True)
        )

        content1 = self.loop.run_until_complete(read_screen(term1))
        content2 = self.loop.run_until_complete(read_screen(term2))

        self.assertIn("李田所", content1)
        self.assertIn("人类有三大欲望", content2)

        self.loop.run_until_complete(close_terminal(term1))
        self.loop.run_until_complete(close_terminal(term2))
        self.assertNotIn(term1, terminals)
        self.assertNotIn(term2, terminals)

    def test_error_handling(self):
        """测试错误处理"""
        tools = terminal_toolset.get_tools()
        send_string = tools["terminal_send_string"]["func"]
        read_screen = tools["terminal_read_screen"]["func"]
        close_terminal = tools["terminal_close"]["func"]

        result = self.loop.run_until_complete(
            send_string("nonexistent", "echo test", with_enter=True)
        )
        self.assertIn("错误：未找到终端", result)

        result = self.loop.run_until_complete(read_screen("nonexistent"))
        self.assertIn("错误：未找到终端", result)

        result = self.loop.run_until_complete(close_terminal("nonexistent"))
        self.assertIn("错误：未找到终端", result)


if __name__ == "__main__":
    unittest.main()
