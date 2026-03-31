import unittest
import asyncio
from linhai.machine_control.master_host import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    close_all_terminals,
    terminals,
)


class TestTerminalToolset(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.run_until_complete(asyncio.to_thread(close_all_terminals))
        self.loop.close()

    def test_terminal_lifecycle(self):
        term_id = self.loop.run_until_complete(terminal_create(columns=80, lines=24))
        self.assertIsNotNone(term_id)
        self.assertIn(term_id, terminals)

        result = self.loop.run_until_complete(
            terminal_send_string(term_id, "echo '114514'", with_enter=True)
        )
        self.assertIn("114514", result)

        screen_content = self.loop.run_until_complete(terminal_read_screen(term_id))
        self.assertIn("114514", screen_content)

        result = self.loop.run_until_complete(terminal_send_keys(term_id, ["ctrl+l"]))
        self.assertIn("已发送按键", result)

        result = self.loop.run_until_complete(terminal_close(term_id))
        self.assertIn("已关闭终端", result)
        self.assertNotIn(term_id, terminals)

    def test_multiple_terminals(self):
        term1 = self.loop.run_until_complete(terminal_create())
        term2 = self.loop.run_until_complete(terminal_create())

        self.loop.run_until_complete(
            terminal_send_string(term1, "echo '李田所'", with_enter=True)
        )
        self.loop.run_until_complete(
            terminal_send_string(term2, "echo '人类有三大欲望'", with_enter=True)
        )

        content1 = self.loop.run_until_complete(terminal_read_screen(term1))
        content2 = self.loop.run_until_complete(terminal_read_screen(term2))

        self.assertIn("李田所", content1)
        self.assertIn("人类有三大欲望", content2)

        self.loop.run_until_complete(terminal_close(term1))
        self.loop.run_until_complete(terminal_close(term2))
        self.assertNotIn(term1, terminals)
        self.assertNotIn(term2, terminals)

    def test_error_handling(self):
        result = self.loop.run_until_complete(
            terminal_send_string("nonexistent", "echo test", with_enter=True)
        )
        self.assertIn("错误：未找到终端", result)

        result = self.loop.run_until_complete(terminal_read_screen("nonexistent"))
        self.assertIn("错误：未找到终端", result)

        result = self.loop.run_until_complete(terminal_close("nonexistent"))
        self.assertIn("错误：未找到终端", result)


if __name__ == "__main__":
    unittest.main()
