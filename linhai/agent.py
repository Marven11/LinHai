import asyncio
import logging
from typing import TypedDict, Any

from linhai.llm import ChatMessage, LanguageModel, AnswerToken, Answer
from linhai.queue import Queue, QueueClosed, select
from linhai.type_hints import AgentState

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
        tool_input_queue: Queue[ChatMessage],
        tool_output_queue: Queue[Any],
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
        self.task_context = {}

        self.messages = [
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

            await self.handle_user_message(chat_msg)

    async def state_working(self):
        """自动运行状态"""
        logger.info("Agent进入自动运行状态")
        while self.state == "working":
            try:
                queues = [self.user_input_queue, self.tool_output_queue]
                async for msg, index in select(*queues):
                    try:
                        if index == 0:
                            await self.handle_user_message(msg)
                        elif index == 1:
                            await self.handle_tool_message(msg)
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

    async def state_paused(self):
        """暂停运行状态"""
        logger.info("Agent进入暂停状态")
        while self.state == "paused":
            try:
                queues = [self.user_input_queue, self.tool_output_queue]
                async for msg, index in select(*queues):
                    try:
                        if index == 0:
                            await self.handle_user_message(msg)
                        elif index == 1:
                            await self.handle_tool_message(msg)
                    except QueueClosed:
                        logger.info("处理消息时队列已关闭")
                        break
            except QueueClosed:
                logger.info("所有队列已关闭")
                break
            except Exception as e:
                logger.error("处理消息时出错: %s", str(e))
                raise RuntimeError("处理消息时出错") from e

    async def handle_user_message(self, msg: ChatMessage):
        """处理用户消息"""
        logger.info("处理用户消息: %s", msg.message)

        self._update_context_from_message(msg)

        self.messages.append(msg)

        try:
            await self._generate_response()
            self.state = "waiting_user"
        except Exception as e:
            logger.error("处理用户消息时出错: %s", str(e))
            self.state = "paused"
            raise RuntimeError("处理用户消息时出错") from e

    async def handle_tool_message(self, msg: ChatMessage):
        """处理工具消息"""
        logger.info("收到工具消息: %s", msg.message)
        self.task_context["last_tool_message"] = msg.message

        self.messages.append(msg)

        await self._generate_response()

    def _update_context_from_message(self, msg: ChatMessage):
        """从用户消息更新上下文"""
        self.task_context["last_user_message"] = msg.message

    async def _generate_response(self):
        """生成回复并发送给用户"""

        response: Answer = await self.config["model"].answer_stream(self.messages)

        async for token in response:
            await self.user_output_queue.put(token)

        await self.user_output_queue.put(response)

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

你是林海漫游，一个思维强大、擅长编程、记忆力强、措辞友好、小心谨慎的人工智能Agent

你有时会出错，有时会健忘，但是你会根据用户的需求和你自己的观察修正自己，完成任务。

# 注意

- 用用户使用的语言进行交流
- 保持友好和专业的态度
- 仔细思考用户的每个请求
- 如果遇到不确定的事情，可以询问用户
"""
