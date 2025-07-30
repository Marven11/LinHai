import argparse
import unittest
import sys
import asyncio
from typing import Sequence

from linhai.config import load_config
from linhai.llm import ChatMessage, OpenAi


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


def main():
    parser = argparse.ArgumentParser(description="LinHai 主程序")
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用命令")

    # 添加test命令
    test_parser = subparsers.add_parser("test", help="运行单元测试")
    
    # 添加chat命令
    chat_parser = subparsers.add_parser("chat", help="与LLM聊天")

    args = parser.parse_args()

    if args.command == "test":
        success = run_tests()
        sys.exit(0 if success else 1)
    elif args.command == "chat":
        config = load_config()
        llm = OpenAi(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"]["base_url"],
            model=config["llm"]["model"],
            openai_config={}
        )
        asyncio.run(chat_loop(llm))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
