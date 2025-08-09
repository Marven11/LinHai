from pathlib import Path
from typing import TypedDict, cast
import asyncio
import logging
import json
import traceback

from linhai.markdown_parser import extract_tool_calls

from linhai.llm import (
    Message,
    ChatMessage,
    LanguageModel,
    AnswerToken,
    Answer,
    OpenAi,
    ToolCallMessage,
    LanguageModelMessage,
)
from linhai.queue import Queue, QueueClosed
from linhai.type_hints import AgentState
from linhai.config import load_config
from linhai.tool.main import ToolManager
from linhai.tool.base import get_tools_info

logger = logging.getLogger(__name__)

WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class AgentRuntimeErrorMessage(Message):
    def __init__(self, message: str):
        self.message = message

    def to_chat_message(self) -> LanguageModelMessage:
        return {"role": "system", "content": self.message}


class AgentConfig(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    model: LanguageModel


class GlobalMemory:
    def __init__(self, filepath: Path):
        assert filepath.exists(), f"{filepath} not exists"
        self.filepath = filepath

    def to_chat_message(self) -> LanguageModelMessage:
        return {
            "role": "system",
            "content": f"# 全局记忆\n\n{self.filepath.read_text()}",
        }


class Agent:
    def __init__(
        self,
        config: AgentConfig,
        user_input_queue: Queue[ChatMessage],
        user_output_queue: Queue[AnswerToken | Answer],
        tool_manager: ToolManager,
    ):
        """
        初始化Agent

        参数:
            config: Agent配置
            user_input_queue: 用户输入消息队列
            user_output_queue: 发送给用户的消息队列
            tool_manager: 工具管理器实例
        """
        self.config = config
        self.user_input_queue = user_input_queue
        self.user_output_queue = user_output_queue
        self.tool_manager = tool_manager

        self.state: AgentState = "waiting_user"

        self.messages: list[Message] = [
            ChatMessage(
                role="system", message=self.config["system_prompt"], name="system"
            ),
        ]

        # 加载全局记忆
        memory_config = config.get("memory", {})
        memory_filepath = Path(memory_config.get("file_path", "./LINHAI.md"))
        if memory_filepath.exists():
            self.messages.append(GlobalMemory(memory_filepath))

    async def state_waiting_user(self):
        """等待用户状态"""
        logger.info("Agent进入等待用户状态")
        while self.state == "waiting_user":
            chat_msg = await self.user_input_queue.get()
            if chat_msg is None:
                break

            await self.handle_messages([chat_msg])

    async def state_working(self):
        """自动运行状态"""
        logger.info("Agent进入自动运行状态")
        # 直接处理用户输入消息
        if not self.user_input_queue.empty():
            try:
                msg = await self.user_input_queue.get()
                await self.handle_messages([cast(ChatMessage, msg)])
            except QueueClosed:
                logger.info("用户输入队列已关闭")
            except Exception as e:
                logger.error("处理消息时出错: %s", str(e))
                self.state = "paused"
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

    async def state_paused(self):
        """暂停运行状态"""
        logger.info("Agent进入暂停运行状态")
        try:
            msg = await self.user_input_queue.get()
            await self.handle_messages([cast(ChatMessage, msg)])
        except QueueClosed:
            logger.info("用户输入队列已关闭")
        except Exception as e:
            logger.error("处理消息时出错: %s", str(e))
            raise RuntimeError("处理消息时出错") from e

    async def call_tool(self, tool_call: ToolCallMessage):
        """直接调用工具并处理结果"""
        try:
            tool_result = await self.tool_manager.process_tool_call(tool_call)
            self.messages.append(tool_result)
            self.state = "working"
        except Exception as e:
            logger.error(f"工具调用失败: {str(e)}")
            self.state = "paused"

    async def handle_messages(self, messages: list[Message]):
        """处理新的消息"""
        self.messages += messages
        try:
            return await self.generate_response()
        except Exception:
            self.state = "paused"
            raise

    async def generate_response(self):
        """生成回复并发送给用户"""
        response: Answer = await self.config["model"].answer_stream(self.messages)

        async for token in response:
            await self.user_output_queue.put(token)

        await self.user_output_queue.put(response)

        chat_message = cast(ChatMessage, response.get_message())
        full_response = chat_message.message

        tool_calls = extract_tool_calls(full_response)

        for call in tool_calls:
            try:
                if "name" in call and "arguments" in call:
                    tool_call = ToolCallMessage(
                        function_name=call["name"],
                        function_arguments=json.dumps(call["arguments"]),
                    )
                    await self.call_tool(tool_call)
                    self.state = "working"
            except Exception:
                traceback.print_exc()
                continue

        self.messages.append(chat_message)

        if WAITING_USER_MARKER in full_response:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                self.messages.append(
                    AgentRuntimeErrorMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            elif tool_calls:
                self.messages.append(
                    AgentRuntimeErrorMessage(
                        f"添加{WAITING_USER_MARKER!r}的同时调用了工具，暂停自动运行失败，你可能需要等待工具的调用结果。"
                        f"你不应该在调用了工具时请求等待用户的回答"
                    )
                )
            else:
                self.state = "waiting_user"
        elif self.state == "working" and not tool_calls:
            self.messages.append(
                AgentRuntimeErrorMessage(
                    f"警告：你既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答，"
                    f"你需要使用{WAITING_USER_MARKER!r}等待用户回答，否则你收不到用户的消息"
                )
            )

    async def run(self):
        """Agent主循环"""
        logger.info("Agent启动")
        while True:
            try:
                if self.state == "waiting_user":
                    await self.state_waiting_user()
                elif self.state == "working":
                    await self.state_working()
                elif self.state == "paused":
                    await self.state_paused()
                else:
                    logger.error("遇到未知状态: %s，退出运行循环", self.state)
                    break

            except asyncio.CancelledError:
                logger.info("Agent任务被取消")
                break
            except Exception as e:
                logger.error("Agent运行出错: %s", str(e))
                self.state = "paused"
                raise RuntimeError("Agent运行出错") from e
            await asyncio.sleep(0)


DEFAULT_SYSTEM_PROMPT = """
# 情景

你是林海漫游，一个思维强大、擅长编程、记忆力强、措辞友好、小心谨慎、回复简洁的人工智能Agent

你有时会出错，有时会健忘，但是你会根据用户的需求和你自己的观察修正自己，完成任务。

# 风格

- 如果用户有指定你的回答风格, 按照用户的做, 否则继续往下看
- 不要废话: 用简洁的语言回答, 能用一句话回复就不要用两句

# 工具

你可以使用Markdown中的JSON code block调用工具，格式如下:

```json
{
    "name": "工具名称",
    "arguments": {
        "参数1": "值1",
        "参数2": "值2"
    }
}
```

所有工具如下:

TOOLS

注意:

- 你需要积极使用工具，如果能用工具完成的任务就用工具完成
- 工具调用必须使用上述JSON格式的code block
- 避免复读工具的输出

# 状态转义

你有两个状态：等待用户、自动运行

1. 等待用户：你等待用户的下一条消息
2. 自动运行：你为了完成用户的任务，自动调用工具与外界交互

如果你完成了任务，或者需要等待用户回答一些问题，你可以在回答的最后一行加上`#LINHAI_WAITING_USER`等待用户回答。
"""


def create_agent(
    config_path: str = "./config.toml",
) -> tuple[Agent, Queue[ChatMessage], Queue[AnswerToken | Answer], ToolManager]:
    """创建并配置Agent实例
    参数:
        config_path: 配置文件路径
    返回:
        tuple[Agent, 用户输入队列, 用户输出队列, ToolManager实例]
    """
    config = load_config(config_path)
    tools_info = get_tools_info()

    llm = OpenAi(
        api_key=config["llm"]["api_key"],
        base_url=config["llm"]["base_url"],
        model=config["llm"]["model"],
        openai_config={},
    )

    user_input_queue: Queue[ChatMessage] = Queue()
    user_output_queue: Queue[AnswerToken | Answer] = Queue()

    system_prompt = DEFAULT_SYSTEM_PROMPT.replace(
        "TOOLS", json.dumps(tools_info, ensure_ascii=False, indent=2)
    )

    agent_config: AgentConfig = {"system_prompt": system_prompt, "model": llm}

    tool_manager = ToolManager()

    agent = Agent(
        config=agent_config,
        user_input_queue=user_input_queue,
        user_output_queue=user_output_queue,
        tool_manager=tool_manager,
    )

    return agent, user_input_queue, user_output_queue, tool_manager
