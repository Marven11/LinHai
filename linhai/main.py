"""
LinHai 主程序入口模块。

提供命令行接口，支持运行测试和Agent模式。
"""

from pathlib import Path
import asyncio
import argparse
import unittest
import sys

import uvicorn

from linhai.init import InitApp
from linhai.config import get_default_config_path
from linhai.tui import TUIApp
from linhai.base import Message
from linhai.registry import Registry


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


async def run_init(config_path: Path | None = None):
    """运行初始化配置TUI。"""

    if config_path is None:
        config_path = get_default_config_path()

    if config_path.exists():
        print(f"错误: 配置文件已存在: {config_path}")
        print("请先删除或备份现有配置文件后再运行初始化命令。")
        return 1

    app = InitApp(config_path=config_path)
    await app.run_async()
    return 0


def run_webui(args):
    """运行WebUI服务。"""
    from linhai.webui import create_app
    from linhai.webui.agent_manager import AgentManager

    config_path = args.config or get_default_config_path()
    AgentManager(config_path=config_path)

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


async def run(args):
    """运行LinHai应用"""
    from linhai.config import load_config
    from linhai.agent.create import create_agent_from_context
    from linhai.agent.create import create_agent_build_context

    registry = Registry()
    registry.register_member("cli_args", args)

    from linhai.config import get_default_config_path

    config_path = (
        Path(args.config).expanduser() if args.config else get_default_config_path()
    )
    config = load_config(config_path)

    from linhai.agent.create import AgentBuildArguments

    build_args: AgentBuildArguments = {
        "rss": args.rss,
        "telegram": args.telegram,
        "disable_waiting_marker": args.disable_waiting_marker,
        "afk": args.afk,
        "claw_enabled": args.claw,
        "claw_folder": args.claw_folder,
        "message": args.message,
        "file": args.file,
        "planning": args.planning,
        "llm_name": args.llm,
        "checklist_path": args.checklist,
        "profile_name": args.profile,
        "git_worktree": args.git_worktree,
    }
    context = create_agent_build_context(
        registry=registry,
        config=config,
        config_basedir=config_path.parent,
        build_args=build_args,
    )
    _agent = await create_agent_from_context(context)

    app = TUIApp(
        registry=registry,
        tui_config=config.tui,
        init_messages=context["message"],
        init_files=context["file"],
    )

    registry.call_postinit()

    await app.run_async()
    return app.return_code


def main():
    """主函数，解析命令行参数并执行相应命令。"""

    parser = argparse.ArgumentParser(description="LinHai 主程序")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="配置文件路径（默认：~/.config/linhai/config.toml）",
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
        "--profile",
        type=str,
        default=None,
        help="指定使用的Agent profile名称（默认使用第一个profile）",
    )
    parser.add_argument(
        "--checklist",
        type=Path,
        help="检查清单文件路径，包含一系列代码要求，如./CODE_REQUIREMENTS.md",
    )
    parser.add_argument(
        "--planning",
        action="store_true",
        help="启用文档规划模式",
    )
    parser.add_argument(
        "--afk",
        action="store_true",
        help="禁止Agent使用....暂停",
    )
    parser.add_argument(
        "--disable-waiting-marker",
        action="store_true",
        help="临时关闭出现 #LINHAI_WAITING_USER 才暂停的功能",
    )
    parser.add_argument(
        "--claw",
        action="store_true",
        help="启用 Continuous Living Autonomous Worker 模式",
    )
    parser.add_argument(
        "--claw-folder",
        type=Path,
        default=None,
        help="指定claw目录路径（默认：~/.local/share/linhai/claw）",
    )
    parser.add_argument(
        "--rss",
        type=str,
        action="append",
        default=[],
        help="RSS feed URL，可指定多个",
    )
    parser.add_argument(
        "--telegram",
        action="store_true",
        help="启用Telegram远程控制功能",
    )
    parser.add_argument(
        "--git-worktree",
        action="store_true",
        help="在conversation目录中创建当前git项目的worktree作为工作目录",
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    init_parser = subparsers.add_parser("init", help="初始化LinHai配置文件")
    init_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="配置文件路径（默认：~/.config/linhai/config.toml）",
    )

    webui_parser = subparsers.add_parser("webui", help="启动WebUI服务")
    webui_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="WebUI服务监听地址",
    )
    webui_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="WebUI服务监听端口",
    )
    webui_parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="配置文件路径（默认：~/.config/linhai/config.toml）",
    )

    args = parser.parse_args()

    if args.config is None and args.command not in ("init", "webui"):
        args.config = get_default_config_path()

    if args.command == "init":
        return_code = asyncio.run(run_init(config_path=args.config))
    elif args.command == "webui":
        return_code = run_webui(args)
    else:
        return_code = asyncio.run(run(args))

    sys.exit(return_code)


if __name__ == "__main__":
    main()
