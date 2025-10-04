"""
LinHai 主程序入口模块。

提供命令行接口，支持运行测试和Agent模式。
"""

from pathlib import Path
import argparse
import unittest

from linhai.agent import create_agent
from linhai.cli_ui import CLIApp


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


def main():
    """主函数，解析命令行参数并执行相应命令。"""
    parser = argparse.ArgumentParser(description="LinHai 主程序")
    parser.add_argument(
        "--config",
        type=Path,
        default="~/.config/linhai/config.toml",
        help="配置文件路径",
    )
    parser.add_argument("-m", "--message", type=str, help="初始用户消息")

    args = parser.parse_args()

    # 处理初始消息
    init_messages: list["Message"] | None = None
    if args.message:
        from linhai.llm import ChatMessage, Message

        init_messages = [ChatMessage(role="user", message=args.message)]

    (
        agent,
        input_queue,
        output_queue,
        tool_request_queue,
        tool_confirmation_queue,
        _,
    ) = create_agent(args.config.expanduser(), init_messages)
    app = CLIApp(
        agent,
        input_queue,
        output_queue,
        tool_request_queue,
        tool_confirmation_queue,
        init_message=args.message,
    )
    app.run()


if __name__ == "__main__":
    main()
