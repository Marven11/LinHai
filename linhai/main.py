import argparse
import unittest
import sys
import asyncio
from typing import Sequence

from linhai.config import load_config
from linhai.llm import ChatMessage, OpenAi
from linhai.agent import Agent, AgentConfig
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
    history: Sequence[ChatMessage] = []

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


def create_agent(config_path: str = "./config.toml") -> tuple[Agent, Queue, Queue]:
    """创建并配置Agent实例
    参数:
        config_path: 配置文件路径
    """
    config = load_config(config_path)
    llm = OpenAi(
        api_key=config["llm"]["api_key"],
        base_url=config["llm"]["base_url"],
        model=config["llm"]["model"],
        openai_config={},
    )

    # 创建Agent所需队列
    user_input_queue = Queue()
    user_output_queue = Queue()
    tool_input_queue = Queue()
    tool_output_queue = Queue()

    # 创建Agent配置
    agent_config: AgentConfig = {"system_prompt": "你是一个智能助手", "model": llm}

    # 创建Agent实例
    agent = Agent(
        config=agent_config,
        user_input_queue=user_input_queue,
        user_output_queue=user_output_queue,
        tool_input_queue=tool_input_queue,
        tool_output_queue=tool_output_queue,
    )

    return agent, user_input_queue, user_output_queue


async def agent_chat_loop(agent: Agent, input_queue: Queue, output_queue: Queue):
    """与Agent进行交互式聊天"""
    print("输入'quit'退出聊天")

    # 启动Agent运行
    agent_task = asyncio.create_task(agent.run())

    try:
        while True:
            # 获取用户输入
            user_input = input("\nYou: ")
            if user_input.lower() == "quit":
                break

            # 发送用户消息
            await input_queue.put(ChatMessage("user", user_input))

            # 接收Agent回复
            print("\nAI: ", end="", flush=True)
            while True:
                output = await output_queue.get()
                if hasattr(output, "get_message"):  # 完整回答
                    break
                print(output["content"], end="", flush=True)
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
        agent, input_queue, output_queue = create_agent(args.config)
        asyncio.run(agent_chat_loop(agent, input_queue, output_queue))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
