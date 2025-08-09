from typing import Sequence
import argparse
import unittest
import sys
import asyncio

from linhai.config import load_config
from linhai.llm import ChatMessage, OpenAi, Message, AnswerToken, Answer
from linhai.agent import Agent, create_agent
from linhai.queue import Queue


def run_tests():
    """运行所有单元测试"""
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir="linhai/tests", pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


async def chat_loop(llm: OpenAi):
    """与LLM进行交互式聊天"""
    history: Sequence[Message] = []

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


async def agent_chat_loop(agent: Agent, input_queue: Queue, output_queue: Queue[AnswerToken | Answer]):
    """与Agent进行交互式聊天"""
    print("输入'quit'退出聊天")

    agent_task = asyncio.create_task(agent.run())

    try:
        while True:
            if agent.state == "waiting_user":
                user_input = input("\nYou: ")
                if user_input.lower() == "quit":
                    break

                await input_queue.put(ChatMessage("user", user_input))

            print("\nAI: ", end="", flush=True)
            while True:
                output = await output_queue.get()
                if isinstance(output, dict):  # AnswerToken
                    print(output["content"], end="", flush=True)
                else:
                    tool_call = output.get_tool_call()
                    if tool_call:
                        print(f"{tool_call.function_name}(...)", end="")
                    break
            print()

    except KeyboardInterrupt:
        print("\n聊天已中断")
    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


def main():
    parser = argparse.ArgumentParser(description="LinHai 主程序")
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # 添加test命令
    test_parser = subparsers.add_parser("test", help="运行单元测试")

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
        agent, input_queue, output_queue, _ = create_agent(args.config)
        asyncio.run(agent_chat_loop(agent, input_queue, output_queue))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
