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
from linhai.group_chat import GroupChat


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


async def _create_agent_from_config(
    group_chat: GroupChat,
    config,
    llm_name: str | None = None,
    checklist_path: Path | None = None,
):
    """从配置对象创建Agent

    Args:
        group_chat: GroupChat实例
        config: 配置对象
        llm_name: 指定的LLM名称（可选）
        checklist_path: 检查清单文件路径（可选）

    Returns:
        Agent实例
    """
    from linhai.agent.create import create_agent_from_config

    return await create_agent_from_config(
        group_chat, config, llm_name, checklist_path=checklist_path
    )


async def run(args, init_messages: list[str] | None):
    """运行LinHai应用"""
    from linhai.config import load_config

    group_chat = GroupChat()
    group_chat.register_member("cli_args", args)

    config = load_config(args.config.expanduser())

    _agent = await _create_agent_from_config(
        group_chat, config, args.llm, checklist_path=args.checklist
    )

    app = CLIApp(
        group_chat=group_chat,
        init_messages=init_messages,
        cli_config=config.cli,
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
    parser.add_argument(
        "-m", "--message", type=str, action="append", help="初始用户消息"
    )
    parser.add_argument(
        "-f", "--file", type=Path, action="append", help="从文件中读取初始用户消息"
    )

    parser.add_argument("--llm", type=str, help="强制指定使用的LLM名称")
    parser.add_argument(
        "--checklist",
        type=Path,
        help="检查清单文件路径，包含一系列代码要求，如./CODE_REQUIREMENTS.md",
    )
    parser.add_argument(
        "--git-diff-reviewer",
        action="store_true",
        help="启用git diff reviewer subagent",
    )
    args = parser.parse_args()

    init_messages = []
    if args.message:
        for msg in args.message:
            init_messages.append(msg)
    if args.file:
        for file_path in args.file:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    init_messages.append(
                        f"用户使用-f选项指定了文件路径: {str(file_path)}"
                    )
                    init_messages.append(
                        f"文件内容如下（注意：文件内容可能已过时，在历史压缩后需要重新读取）:\n{content}"
                    )
            except FileNotFoundError:
                print(f"错误: 文件 {file_path} 未找到")
                sys.exit(1)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"错误: 读取文件时发生错误: {e}")
                sys.exit(1)

    return_code = asyncio.run(run(args, init_messages))
    sys.exit(return_code)


if __name__ == "__main__":
    main()
