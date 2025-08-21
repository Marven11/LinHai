from pathlib import Path
from typing import TypedDict, cast
from reprlib import Repr
import asyncio
import logging
import json
import traceback

from linhai.markdown_parser import extract_tool_calls, extract_json_blocks
from linhai.exceptions import LLMResponseError
from linhai.llm import (
    Message,
    ChatMessage,
    LanguageModel,
    AnswerToken,
    Answer,
    OpenAi,
    OpenAiAnswer,
    ToolCallMessage,
    LanguageModelMessage,
)
from asyncio import Queue, QueueEmpty
from linhai.type_hints import AgentState
from linhai.config import load_config
from linhai.tool.main import ToolManager
from linhai.tool.base import get_tools_info
from linhai.prompt import DEFAULT_SYSTEM_PROMPT, COMPRESS_HISTORY_PROMPT

logger = logging.getLogger(__name__)

repr_obj = Repr(maxstring=50)

WAITING_USER_MARKER = "#LINHAI_WAITING_USER"


class AgentRuntimeErrorMessage(Message):
    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "system", "content": self.message}


class OpenAiUsage(Message):
    def __init__(self, total_tokens: int):
        self.total_tokens = total_tokens

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "system",
            "content": f"当前token总用量为: {self.total_tokens} ({self.total_tokens/1000:.2f} k)",
        }


class CompressRequest(Message):
    def __init__(self, messages_summerization: str):
        self.messages_summerization = messages_summerization

    def to_llm_message(self) -> LanguageModelMessage:
        prompt = COMPRESS_HISTORY_PROMPT.replace(
            "{|SUMMERIZATION|}", "\n".join(self.messages_summerization)
        )
        return {
            "role": "system",
            "content": prompt,
        }


class AgentConfig(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    model: LanguageModel
    compress_threshold: float


class GlobalMemory:
    def __init__(self, filepath: Path):
        assert filepath.exists(), f"{filepath} not exists"
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        return {
            "role": "system",
            "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，内容如下

{self.filepath.read_text()}
""",
        }


class Agent:
    def __init__(
        self,
        config: AgentConfig,
        user_input_queue: "Queue[ChatMessage]",
        user_output_queue: "Queue[AnswerToken | Answer]",
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
            except QueueEmpty:
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
        except QueueEmpty:
            logger.info("用户输入队列已关闭")
        except Exception as e:
            logger.error("处理消息时出错: %s", str(e))
            raise RuntimeError("处理消息时出错") from e

    async def compress(self):
        messages = [msg.to_llm_message() for msg in self.messages]
        messages_summerization = "\n".join(
            f"- id: {i} role: {msg["role"]!r} content: {repr_obj.repr(msg.get('content', None))}"
            for i, msg in enumerate(messages)
        )
        self.messages.append(CompressRequest(messages_summerization))
        answer = await self.generate_response(enable_compress=False)
        try:
            scores_data = extract_json_blocks(
                str(answer.get_message().to_llm_message().get("content", ""))
            )
            if len(scores_data) != 1:
                raise LLMResponseError("数据数量有误")
            scores = scores_data.pop()
            todelete_indicies = set(
                int(info.get("id", "-1"))
                for info in scores
                if float(info.get("score", "10") < 8)
            )
            self.messages = [
                msg
                for idx, msg in enumerate(self.messages)
                if (idx in todelete_indicies and idx >= 2)
                or isinstance(msg, CompressRequest)
            ]
            self.messages.append(
                ChatMessage(
                    role="system",
                    message="压缩已经完成，你可以继续完成工作或者向用户报告了",
                )
            )
        except LLMResponseError:
            self.messages.append(
                ChatMessage(
                    role="system",
                    message="错误：你没有输出需要的score，请调用工具重新启动流程",
                )
            )

    async def call_tool(self, tool_call: ToolCallMessage):
        """直接调用工具并处理结果"""
        try:
            tool_result = await self.tool_manager.process_tool_call(tool_call)
            self.messages.append(
                ChatMessage(
                    role="system",
                    message=f"你调用了工具{tool_call.function_name!r}，结果如下",
                )
            )
            self.messages.append(tool_result)
            if self.state == "waiting_user":
                self.state = "working"
        except Exception as e:
            msg = f"工具调用失败: {str(e)} {repr(e)}"
            logger.error(msg)
            # deepseek v3.1 如果这里没有用户消息，则会变成以assitant消息结尾
            # 然后就会生成失败，因此加上一条兜底的用户消息
            self.messages.append(
                ChatMessage(
                    role="user",
                    message=msg,
                )
            )
            self.state = "paused"

    async def handle_messages(self, messages: list[Message]):
        """处理新的消息"""
        self.messages += messages
        try:
            return await self.generate_response()
        except Exception:
            self.state = "paused"
            raise

    async def generate_response(self, enable_compress: bool = True) -> Answer:
        """生成回复并发送给用户"""
        answer: Answer = await self.config["model"].answer_stream(self.messages)

        async for token in answer:
            await self.user_output_queue.put(token)
            if not self.user_input_queue.empty():
                await self.user_output_queue.put(answer)
                chat_message = cast(ChatMessage, answer.get_message())
                self.messages.append(chat_message)
                self.messages.append(
                    ChatMessage(role="system", message="用户打断了你的回答")
                )
                self.messages.append(await self.user_input_queue.get())
                answer.interrupt()
                return await self.generate_response()

        await self.user_output_queue.put(answer)

        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message
        self.messages.append(chat_message)

        tool_calls = extract_tool_calls(full_response)

        for call in tool_calls:
            try:
                if call.get("name") == "compress_history":
                    if enable_compress:
                        await self.compress()
                    else:
                        self.messages.append(
                            ChatMessage(
                                role="system",
                                message="当前禁止调用compress_history工具，你是不是弄错什么了？",
                            )
                        )
                    return await self.generate_response()
                if "name" in call and "arguments" in call:
                    tool_call = ToolCallMessage(
                        function_name=call["name"],
                        function_arguments=json.dumps(call["arguments"]),
                    )
                    await self.call_tool(tool_call)
            except Exception:
                traceback.print_exc()
                continue

        if WAITING_USER_MARKER in full_response:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                self.messages.append(
                    AgentRuntimeErrorMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
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

        if isinstance(answer, OpenAiAnswer):
            if enable_compress and answer.total_tokens > self.config.get(
                "compress_threshold", 65536 * 0.8
            ):
                await self.compress()
                return await self.generate_response()

        return answer

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


def create_agent(
    config_path: str = "./config.toml",
) -> tuple[Agent, "Queue[ChatMessage]", "Queue[AnswerToken | Answer]", ToolManager]:
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

    user_input_queue: "Queue[ChatMessage]" = Queue()
    user_output_queue: "Queue[AnswerToken | Answer]" = Queue()

    system_prompt = DEFAULT_SYSTEM_PROMPT.replace(
        "{|TOOLS|}", json.dumps(tools_info, ensure_ascii=False, indent=2)
    )

    agent_config: AgentConfig = {
        "system_prompt": system_prompt,
        "model": llm,
        "compress_threshold": float(config.get("compress_threshold", 65536 * 0.8)),
    }

    tool_manager = ToolManager()

    agent = Agent(
        config=agent_config,
        user_input_queue=user_input_queue,
        user_output_queue=user_output_queue,
        tool_manager=tool_manager,
    )

    return agent, user_input_queue, user_output_queue, tool_manager
