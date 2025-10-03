"""
LinHai 主程序入口模块。

提供命令行接口，支持运行测试和Agent模式。
"""

import argparse
import unittest
import sys

from linhai.config import load_config
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
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # 添加test命令
    subparsers.add_parser("test", help="运行单元测试")

    # 添加agent命令
    agent_parser = subparsers.add_parser("agent", help="与Agent聊天")
    agent_parser.add_argument(
        "--config", type=str, default="~/.config/linhai/config.toml", help="配置文件路径"
    )

    args = parser.parse_args()

    if args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)

    elif args.command == "agent":

        (
            agent,
            input_queue,
            output_queue,
            tool_request_queue,
            tool_confirmation_queue,
            _,
        ) = create_agent(args.config)
        app = CLIApp(
            agent,
            input_queue,
            output_queue,
            tool_request_queue,
            tool_confirmation_queue,
        )
        app.run()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
