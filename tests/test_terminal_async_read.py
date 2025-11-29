"""测试PyteTerminal的异步读取功能"""

import unittest
import asyncio
from linhai.tool.tools.terminal import PyteTerminal


class TestPyteTerminalAsyncRead(unittest.TestCase):
    """测试PyteTerminal异步读取功能"""

    def setUp(self):
        """设置测试环境"""
        # 创建新的事件循环
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.terminal = PyteTerminal(columns=80, lines=24)
        # 启动读取任务
        self.loop.run_until_complete(self.terminal.start_reading())
        # 等待终端启动和任务开始，让事件循环运行
        self.loop.run_until_complete(asyncio.sleep(0.5))

    def tearDown(self):
        """清理测试环境"""
        self.terminal.close()
        # 关闭事件循环
        self.loop.close()

    def test_terminal_creation(self):
        """测试终端创建成功"""
        self.assertIsNotNone(self.terminal.screen)
        self.assertIsNotNone(self.terminal.stream)
        self.assertIsNotNone(self.terminal.loop)
        self.assertFalse(self.terminal._stop_reading)

    def test_send_and_read_output(self):
        """测试发送命令并读取输出"""
        # 发送echo命令
        self.terminal.send("echo '114514'\n")
        # 等待异步读取，让事件循环运行
        self.loop.run_until_complete(asyncio.sleep(0.5))
        
        # 获取屏幕内容
        screen_content = self.terminal.get_screen()
        self.assertIn("114514", screen_content)

    def test_multiple_commands(self):
        """测试连续发送多个命令"""
        commands = [
            "echo '人类有三大欲望'",
            "echo '饮食、繁殖、睡眠'",
            "echo '李田所'"
        ]
        
        for cmd in commands:
            self.terminal.send(cmd + "\n")
            self.loop.run_until_complete(asyncio.sleep(0.3))
        
        # 等待所有内容被读取
        self.loop.run_until_complete(asyncio.sleep(0.5))
        
        screen_content = self.terminal.get_screen()
        self.assertIn("人类有三大欲望", screen_content)
        self.assertIn("饮食、繁殖、睡眠", screen_content)
        self.assertIn("李田所", screen_content)

    def test_send_key(self):
        """测试发送按键"""
        # 发送一些文本
        self.terminal.send("echo 'test'")
        # 发送回车键
        self.terminal.send_key("enter")
        # 等待读取，让事件循环运行
        self.loop.run_until_complete(asyncio.sleep(0.5))
        
        screen_content = self.terminal.get_screen()
        self.assertIn("test", screen_content)

    def test_close_stops_reading(self):
        """测试关闭终端会停止读取任务"""
        self.assertFalse(self.terminal._stop_reading)
        self.assertIsNotNone(self.terminal.loop)
        
        self.terminal.close()
        
        self.assertTrue(self.terminal._stop_reading)

    def test_basic_functionality(self):
        """测试基本功能"""
        # 发送命令并验证可以工作
        self.terminal.send("echo 'basic test'\n")
        self.loop.run_until_complete(asyncio.sleep(0.5))
        
        screen_content = self.terminal.get_screen()
        self.assertIn("basic test", screen_content)

    def test_large_output(self):
        """测试大量输出的处理"""
        # 生成大量输出
        large_text = "x" * 1000
        self.terminal.send(f"echo '{large_text}'\n")
        # 等待异步读取处理大量数据，让事件循环运行
        self.loop.run_until_complete(asyncio.sleep(1))
        
        screen_content = self.terminal.get_screen()
        # 屏幕应该包含部分内容（终端有滚动）
        self.assertIn("x", screen_content)


if __name__ == "__main__":
    unittest.main()
