import asyncio
import logging
from typing import TypedDict, Any, cast

from linhai.llm import (
    Message,
    ChatMessage,
    LanguageModel,
    AnswerToken,
    Answer,
    OpenAi,
    ToolCallMessage,
)
from linhai.queue import Queue, QueueClosed, select
from linhai.type_hints import AgentState
from linhai.config import load_config
from linhai.tool.main import ToolManager, ToolErrorMessage, ToolResultMessage
from linhai.tool.base import get_tools_info

logger = logging.getLogger(__name__)


class AgentConfig(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    model: LanguageModel


class Agent:
    def __init__(
        self,
        config: AgentConfig,
        user_input_queue: Queue[ChatMessage],
        user_output_queue: Queue[AnswerToken | Answer],
        tool_input_queue: Queue[ToolCallMessage],
        tool_output_queue: Queue[ToolResultMessage | ToolErrorMessage],
    ):
        """
        初始化Agent

        参数:
            config: Agent配置
            user_input_queue: 用户输入消息队列
            user_output_queue: 发送给用户的消息队列
            tool_input_queue: 发送给工具的消息队列
            tool_output_queue: 工具返回结果的消息队列
        """
        self.config = config
        self.user_input_queue = user_input_queue
        self.user_output_queue = user_output_queue
        self.tool_input_queue = tool_input_queue
        self.tool_output_queue = tool_output_queue

        self.state: AgentState = "waiting_user"
        self.memory = {"language": "zh-CN"}

        self.messages: list[Message] = [
            ChatMessage(
                role="system", message=self.config["system_prompt"], name="system"
            )
        ]

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
        is_tool_message_received = False
        messages: list[Message] = []
        logger.info("Agent进入自动运行状态")
        while not is_tool_message_received:
            try:
                queues = [self.user_input_queue, self.tool_output_queue]
                async for msg, index in select(*queues):
                    try:
                        if index == 0:
                            messages.append(cast(ChatMessage, msg))
                        elif index == 1:
                            messages.insert(
                                0, cast(ToolResultMessage | ToolErrorMessage, msg)
                            )
                            is_tool_message_received = True
                            break
                    except QueueClosed:
                        logger.info("处理消息时队列已关闭")
                        break
            except QueueClosed:
                logger.info("所有队列已关闭")
                break
            except Exception as e:
                logger.error("处理消息时出错: %s", str(e))
                self.state = "paused"
                raise RuntimeError("处理消息时出错") from e
        await self.handle_messages(messages)

    async def state_paused(self):
        """暂停运行状态"""
        messages: list[Message] = []
        logger.info("Agent进入暂停运行状态")
        while self.state == "working":
            try:
                queues = [self.user_input_queue, self.tool_output_queue]
                async for msg, index in select(*queues):
                    try:
                        if index == 0:
                            messages.append(cast(ChatMessage, msg))
                        elif index == 1:
                            messages.insert(
                                0, cast(ToolResultMessage | ToolErrorMessage, msg)
                            )
                            break
                    except QueueClosed:
                        logger.info("处理消息时队列已关闭")
                        break
            except QueueClosed:
                logger.info("所有队列已关闭")
                break
            except Exception as e:
                logger.error("处理消息时出错: %s", str(e))
                self.state = "paused"
                raise RuntimeError("处理消息时出错") from e

        await self.handle_messages(messages)

    async def call_tool(self, tool_call: ToolCallMessage):
        """调用工具并发送请求"""
        await self.tool_input_queue.put(tool_call)
        self.state = "working"  # 进入自动运行状态等待工具结果

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

        # 普通回复处理
        async for token in response:
            await self.user_output_queue.put(token)

        await self.user_output_queue.put(response)

        # 检查是否需要调用工具
        tool_call = response.get_tool_call()
        if tool_call:
            await self.call_tool(tool_call)
            self.state = "working"
        else:
            self.state = "waiting_user"

        assistant_msg = response.get_message()
        self.messages.append(assistant_msg)

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

                # 不再需要pending_tool_call检查
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

- 如果用户有指定你的回答风格，按照用户的做，否则继续往下看
- 不要废话：用简洁的语言回答，能用一句话回复就不要用两句
- 活跃气氛：使用“对不起喵”安抚用户，适当使用emoji，但是不要用除了🐱之外的猫emoji

# 工具

你可以使用Function Calling调用工具

- 你需要积极使用工具，如果能用工具完成的任务就用工具完成

# 状态转义

你有两个状态：等待用户、自动运行

1. 等待用户：你等待用户的下一条消息
2. 自动运行：你为了完成用户的任务，自动调用工具与外界交互
    - 此时没有必要则不要与用户对话
    - 调用完工具，开始回答用户之后自动转到等待用户状态

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
        tools=tools_info,
    )

    user_input_queue: Queue[ChatMessage] = Queue()
    user_output_queue: Queue[AnswerToken | Answer] = Queue()
    tool_input_queue: Queue[ToolCallMessage] = Queue()
    tool_output_queue: Queue[Any] = Queue()

    system_prompt = DEFAULT_SYSTEM_PROMPT

    agent_config: AgentConfig = {"system_prompt": system_prompt, "model": llm}

    agent = Agent(
        config=agent_config,
        user_input_queue=user_input_queue,
        user_output_queue=user_output_queue,
        tool_input_queue=tool_input_queue,
        tool_output_queue=tool_output_queue,
    )

    tool_manager = ToolManager(
        tool_input_queue=tool_input_queue, tool_output_queue=tool_output_queue
    )

    return agent, user_input_queue, user_output_queue, tool_manager
