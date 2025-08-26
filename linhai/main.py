"""
LinHai 主程序入口模块。

提供命令行接口，支持运行测试、聊天和Agent模式。
"""

from typing import List
import argparse
import unittest
import sys
import asyncio

from linhai.config import load_config
from linhai.llm import ChatMessage, OpenAi, Message
from linhai.agent import create_agent
from linhai.cli_ui import CLIApp


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


async def chat_loop(llm: OpenAi):
    """与LLM进行交互式聊天"""
    history: List[Message] = []

    print("输入'quit'退出聊天")
    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() == "quit":
                break

            history.append(ChatMessage("user", user_input))

            print("\nAI: ", end="", flush=True)
            answer = await llm.answer_stream(history)
            async for token in answer:
                print(token["content"], end="", flush=True)

            history.append(answer.get_message())

        except KeyboardInterrupt:
            print("\n聊天已中断")
            break


def main():
    """主函数，解析命令行参数并执行相应命令。"""
    parser = argparse.ArgumentParser(description="LinHai 主程序")
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # 添加test命令
    subparsers.add_parser("test", help="运行单元测试")

    # 添加chat命令
    chat_parser = subparsers.add_parser("chat", help="与LLM聊天")
    chat_parser.add_argument(
        "--config", type=str, default="./config.toml", help="配置文件路径"
    )

    # 添加agent命令
    agent_parser = subparsers.add_parser("agent", help="与Agent聊天")
    agent_parser.add_argument(
        "--config", type=str, default="./config.toml", help="配置文件路径"
    )

    args = parser.parse_args()

    if args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    elif args.command == "chat":
        config = load_config(args.config)
        llm = OpenAi(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"]["base_url"],
            model=config["llm"]["model"],
            openai_config={},
        )
        asyncio.run(chat_loop(llm))
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
