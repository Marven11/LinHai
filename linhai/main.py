"""
LinHai 主程序入口模块。

提供命令行接口，支持运行测试和Agent模式。
"""

from pathlib import Path
import asyncio
import argparse
import unittest
import sys


from linhai.cli import CLIApp
from linhai.agent.base import Message
from linhai.group_chat import GroupChat


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


async def run(args):
    """运行LinHai应用"""
    from linhai.config import load_config
    from linhai.agent.create import create_agent_from_config
    from linhai.agent.create import create_agent_build_context

    group_chat = GroupChat()
    group_chat.register_member("cli_args", args)

    config_path = Path(args.config).expanduser()
    config = load_config(config_path)

    context = create_agent_build_context(
        group_chat=group_chat,
        config=config,
        config_basedir=config_path.parent,
        llm_name=args.llm,
        checklist_path=args.checklist,
        cli_args=args,
    )
    _agent = await create_agent_from_config(context)

    app = CLIApp(
        group_chat=group_chat,
        cli_config=config.cli,
    )

    group_chat.call_postinit()

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
    parser.add_argument(
        "-m", "--message", type=str, action="append", default=[], help="初始用户消息"
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        action="append",
        default=[],
        help="从文件中读取初始用户消息",
    )

    parser.add_argument("--llm", type=str, help="强制指定使用的LLM名称")
    parser.add_argument(
        "--checklist",
        type=Path,
        help="检查清单文件路径，包含一系列代码要求，如./CODE_REQUIREMENTS.md",
    )
    args = parser.parse_args()

    return_code = asyncio.run(run(args))
    sys.exit(return_code)


if __name__ == "__main__":
    main()
