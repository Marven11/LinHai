"""
LinHai 主程序入口模块。

提供命令行接口，支持运行测试和Agent模式。
"""

from pathlib import Path
import asyncio
import argparse
import unittest
import sys

from linhai.agent import create_agent
from linhai.cli_ui import CLIApp
from linhai.group_chat import GroupChat


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


async def run(args, init_message: str):

    group_chat = GroupChat()
    _agent = await create_agent(group_chat, args.config.expanduser(), args.llm)
    app = CLIApp(
        group_chat=group_chat,
        init_message=init_message,
    )
    await app.run_async()
    return app.return_code


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
    parser.add_argument("-f", "--file", type=Path, help="从文件中读取初始用户消息")

    parser.add_argument("--llm", type=str, help="强制指定使用的LLM名称")
    args = parser.parse_args()

    init_message = args.message
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                init_message = (
                    f"用户使用-f选项指定了第一条消息，路径为: {str(args.file)}, 内容如下:\n"
                    + content
                )
        except FileNotFoundError:
            print(f"错误: 文件 {args.file} 未找到")
            sys.exit(1)
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"错误: 读取文件时发生错误: {e}")
            sys.exit(1)

    return_code = asyncio.run(run(args, init_message))
    sys.exit(return_code)

if __name__ == "__main__":
    main()
