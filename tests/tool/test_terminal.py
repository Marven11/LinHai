import unittest
import asyncio
from linhai.machine_control.master_host import (
    terminal_create,
    terminal_send_keys,
    terminal_send_string,
    terminal_read_screen,
    terminal_close,
    close_all_terminals,
)


class TestTerminalTools(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.run_until_complete(asyncio.to_thread(close_all_terminals))
        self.loop.close()

    def test_create_terminal(self):
        async def test():
            result = await terminal_create()
            self.assertIsInstance(result, str)
            self.assertTrue(len(result) > 0)

        self.loop.run_until_complete(test())

    def test_send_string_and_read_screen(self):
        async def test():
            terminal_id = await terminal_create()

            result = await terminal_send_string(
                terminal_id, "echo hello", with_enter=True
            )
            self.assertIn("已发送", result)

            screen_content = await terminal_read_screen(terminal_id)
            self.assertIsInstance(screen_content, str)

            close_result = await terminal_close(terminal_id)
            self.assertIn("已关闭终端", close_result)

        self.loop.run_until_complete(test())

    def test_send_string_without_enter(self):
        async def test():
            terminal_id = await terminal_create()

            result = await terminal_send_string(
                terminal_id, "echo hello", with_enter=False
            )
            self.assertIn("已发送", result)

            await terminal_close(terminal_id)

        self.loop.run_until_complete(test())

    def test_send_keys(self):
        async def test():
            terminal_id = await terminal_create()

            result = await terminal_send_keys(
                terminal_id,
                ["e", "c", "h", "o", "space", "t", "e", "s", "t", "enter"],
            )
            self.assertIn("已发送按键", result)

            await terminal_close(terminal_id)

        self.loop.run_until_complete(test())

    def test_send_special_keys(self):
        async def test():
            terminal_id = await terminal_create()

            result = await terminal_send_keys(
                terminal_id,
                ["up", "down", "left", "right", "tab", "pageup", "pagedown"],
            )
            self.assertIn("已发送按键", result)

            await terminal_close(terminal_id)

        self.loop.run_until_complete(test())

    def test_invalid_terminal_id(self):
        async def test():
            result = await terminal_read_screen("invalid-id")
            self.assertIn("错误：未找到终端", result)

            result = await terminal_send_string("invalid-id", "ls", with_enter=True)
            self.assertIn("错误：未找到终端", result)

            result = await terminal_send_keys("invalid-id", ["a"])
            self.assertIn("错误：未找到终端", result)

            result = await terminal_close("invalid-id")
            self.assertIn("错误：未找到终端", result)

        self.loop.run_until_complete(test())

    def test_invalid_keys(self):
        async def test():
            terminal_id = await terminal_create()

            result = await terminal_send_keys(terminal_id, ["invalid_key"])
            self.assertIn("未知按键", result)

            await terminal_close(terminal_id)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
