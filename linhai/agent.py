from pathlib import Path
from typing import TypedDict, cast, NotRequired
from reprlib import Repr
import asyncio
import logging
import json
import traceback
import datetime

from linhai.markdown_parser import extract_tool_calls, extract_json_blocks
from linhai.exceptions import LLMResponseError
from linhai.llm import (
    Message,
    ChatMessage,
    SystemMessage,
    LanguageModel,
    AnswerToken,
    Answer,
    OpenAi,
    OpenAiAnswer,
    ToolCallMessage,
    ToolConfirmationMessage,
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


class CompressRequest(Message):
    def __init__(self, messages_summerization: str):
        self.messages_summerization = messages_summerization

    def to_llm_message(self) -> LanguageModelMessage:
        prompt = COMPRESS_HISTORY_PROMPT.replace(
            "{|SUMMERIZATION|}", "\n".join(self.messages_summerization)
        )
        return {
            "role": "user",
            "content": prompt,
        }


class RuntimeMessage(Message):
    def __init__(self, message: str):
        self.message = message

    def to_llm_message(self) -> LanguageModelMessage:
        return {"role": "user", "content": f"<runtime>{self.message}</runtime>"}


class AgentConfig(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    model: LanguageModel
    compress_threshold: int
    memory: NotRequired[dict]  # 可选 memory 字段
    tool_confirmation: NotRequired[dict]  # 可选 tool_confirmation 字段


class GlobalMemory:
    def __init__(self, filepath: Path):
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
        tool_request_queue: "Queue[ToolCallMessage]",
        tool_confirmation_queue: "Queue[ToolConfirmationMessage]",
        tool_manager: ToolManager,
    ):
        """
        初始化Agent

        参数:
            config: Agent配置
            user_input_queue: 用户输入消息队列
            user_output_queue: 发送给用户的消息队列
            tool_request_queue: 工具请求队列
            tool_confirmation_queue: 工具确认队列
            tool_manager: 工具管理器实例
        """
        self.config = config
        self.user_input_queue = user_input_queue
        self.user_output_queue = user_output_queue
        self.tool_request_queue = tool_request_queue
        self.tool_confirmation_queue = tool_confirmation_queue
        self.tool_manager = tool_manager

        self.state: AgentState = "waiting_user"

        self.messages: list[Message] = [
            SystemMessage(self.config["system_prompt"]),
        ]

        self.last_token_usage = None
        self.current_enable_compress = True

        # 加载全局记忆
        memory_config = config.get("memory", {})
        memory_filepath = Path(memory_config.get("file_path", "./LINHAI.md")).absolute()
        if memory_filepath.exists():
            self.messages.append(GlobalMemory(memory_filepath))

        # 解析tool_confirmation配置并存储
        tool_confirmation_config = self.config.get("tool_confirmation", {})
        self.skip_confirmation = tool_confirmation_config.get(
            "skip_confirmation", False
        )
        self.whitelist = tool_confirmation_config.get("whitelist", [])
        self.timeout_seconds = tool_confirmation_config.get("timeout_seconds", 30)

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

        if self.last_token_usage > self.config.get(
            "compress_threshold", int(65536 * 0.8)
        ):
            await self.compress()

    async def state_paused(self):
        """暂停运行状态"""
        logger.info("Agent进入暂停运行状态")
        try:
            msg = await self.user_input_queue.get()
            self.state = "waiting_user"
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
                if float(info.get("score", "10")) < 8
            )
            self.messages = [
                msg
                for idx, msg in enumerate(self.messages)
                if idx <= 2
                or (
                    idx not in todelete_indicies
                    and not isinstance(msg, CompressRequest)
                )
            ]
            # Report compression statistics
            original_count = len(messages)
            compressed_count = len(self.messages)
            self.messages.append(
                RuntimeMessage(f"压缩已经完成，消息数量从{original_count}条减少到{compressed_count}条，减少了{original_count - compressed_count}条消息")
            )
        except LLMResponseError as exc:
            self.messages.append(
                RuntimeMessage(
                    f"错误：你没有输出需要的score，请调用工具重新启动流程: {exc!r}"
                )
            )
        except Exception as exc:
            self.messages.append(RuntimeMessage(f"错误：{exc!r}"))

    async def call_tool(self, tool_call: ToolCallMessage) -> bool:
        """直接调用工具并处理结果，返回是否需要进行早期返回"""
        if tool_call.function_name == "compress_history":
            if self.current_enable_compress:
                await self.compress()
            else:
                self.messages.append(
                    RuntimeMessage(
                        "当前禁止调用compress_history工具，你是不是弄错什么了？"
                    )
                )
            return True
        if tool_call.function_name == "get_token_usage":
            if self.last_token_usage is not None:
                self.messages.append(
                    RuntimeMessage(
                        f"当前token总用量为: {self.last_token_usage} "
                        f"({self.last_token_usage/1000:.2f} k)"
                    )
                )
            else:
                self.messages.append(RuntimeMessage("暂无token用量信息"))
            return False

        # 使用存储的tool_confirmation配置（在初始化时解析）
        if self.skip_confirmation or tool_call.function_name in self.whitelist:
            try:
                tool_result = await self.tool_manager.process_tool_call(tool_call)
                self.messages.append(
                    RuntimeMessage(f"你调用了工具{tool_call.function_name!r}，结果如下")
                )
                self.messages.append(tool_result)
                if self.state == "waiting_user":
                    self.state = "working"
                return False  # 不需要早期返回
            except Exception as e:
                msg = f"工具调用失败: {str(e)} {repr(e)}"
                logger.error(msg)
                self.messages.append(RuntimeMessage(msg))
                self.state = "paused"
                return False

        # 需要用户确认：发送工具请求到队列
        await self.tool_request_queue.put(tool_call)
        self.messages.append(
            RuntimeMessage(
                f"已发送工具调用请求: {tool_call.function_name}，等待用户确认..."
            )
        )

        # 使用存储的timeout配置（在初始化时解析）
        timeout_seconds = self.timeout_seconds
        try:
            confirmation = await asyncio.wait_for(
                self.tool_confirmation_queue.get(), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            self.messages.append(
                RuntimeMessage(f"工具调用确认超时（{timeout_seconds}秒），已取消调用")
            )
            return False

        # 检查确认消息是否匹配当前工具调用
        if confirmation.tool_call.function_name != tool_call.function_name:
            self.messages.append(
                RuntimeMessage("错误：收到的确认消息不匹配当前工具调用")
            )
            return False

        # 根据确认状态执行或取消
        if confirmation.confirmed:
            try:
                tool_result = await self.tool_manager.process_tool_call(tool_call)
                self.messages.append(
                    RuntimeMessage(f"你调用了工具{tool_call.function_name!r}，结果如下")
                )
                self.messages.append(tool_result)
                if self.state == "waiting_user":
                    self.state = "working"
                return False  # 不需要早期返回
            except Exception as e:
                msg = f"工具调用失败: {str(e)} {repr(e)}"
                logger.error(msg)
                self.messages.append(RuntimeMessage(msg))
                self.state = "paused"
                return False
        else:
            self.messages.append(
                RuntimeMessage(f"用户取消了工具调用: {tool_call.function_name}")
            )
            return False

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
        # Check if the last message is from assistant, add empty user message if so
        if len(self.messages) > 0:
            last_msg = self.messages[-1]
            if isinstance(last_msg, ChatMessage):
                llm_msg = last_msg.to_llm_message()
                if llm_msg.get("role") == "assistant":
                    empty_user_msg = ChatMessage(role="user", message="")
                    self.messages.append(empty_user_msg)

        self.current_enable_compress = enable_compress
        answer: Answer = await self.config["model"].answer_stream(self.messages)

        async for token in answer:
            await self.user_output_queue.put(token)
            
            # Real-time check for too many tool calls
            current_content = answer.get_current_content()
            json_block_count = current_content.count("```json")
            if json_block_count > 3:
                await self.user_output_queue.put(answer)
                self.messages.append(RuntimeMessage("错误：一次性调用了超过三个工具，最多只能调用三个工具。请分多次调用。"))
                answer.interrupt()
                return await self.generate_response()
            
            if not self.user_input_queue.empty():
                await self.user_output_queue.put(answer)
                chat_message = cast(ChatMessage, answer.get_message())
                self.messages.append(chat_message)
                self.messages.append(RuntimeMessage("用户打断了你的回答"))
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
                if "name" in call and "arguments" in call:
                    tool_call = ToolCallMessage(
                        function_name=call["name"],
                        function_arguments=json.dumps(call["arguments"]),
                    )
                    early_return = await self.call_tool(tool_call)
                    if early_return:
                        return await self.generate_response()
            except Exception:
                traceback.print_exc()
                continue

        if WAITING_USER_MARKER in full_response:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                self.messages.append(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            else:
                self.state = "waiting_user"

        # 检查是否同时调用工具和等待用户
        if tool_calls and WAITING_USER_MARKER in full_response:
            self.messages.append(
                RuntimeMessage(
                    f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                    f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                )
            )
        elif self.state == "working" and not tool_calls:
            self.messages.append(
                RuntimeMessage(
                    f"警告：你既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用），"
                    f"你需要使用{WAITING_USER_MARKER!r}等待用户回答，否则你收不到用户的消息"
                )
            )

        if isinstance(answer, OpenAiAnswer):
            self.last_token_usage = answer.total_tokens

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
) -> tuple[
    Agent,
    "Queue[ChatMessage]",
    "Queue[AnswerToken | Answer]",
    "Queue[ToolCallMessage]",
    "Queue[ToolConfirmationMessage]",
    ToolManager,
]:
    """创建并配置Agent实例
    参数:
        config_path: 配置文件路径
    返回:
        tuple[Agent, 用户输入队列, 用户输出队列, 工具请求队列, 工具确认队列, ToolManager实例]
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
    tool_request_queue: "Queue[ToolCallMessage]" = Queue()
    tool_confirmation_queue: "Queue[ToolConfirmationMessage]" = Queue()

    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_prompt = DEFAULT_SYSTEM_PROMPT.replace(
        "{|TOOLS|}", json.dumps(tools_info, ensure_ascii=False, indent=2)
    ).replace("{|CURRENT_TIME|}", current_time)

    # 确保 config 是字典类型
    config_dict = cast(dict, config)
    # 解析tool_confirmation配置
    tool_confirmation_config = config_dict.get("agent", {}).get("tool_confirmation", {})
    skip_confirmation = tool_confirmation_config.get("skip_confirmation", False)
    whitelist = tool_confirmation_config.get("whitelist", [])

    agent_config: AgentConfig = {
        "system_prompt": system_prompt,
        "model": llm,
        "compress_threshold": int(
            config_dict.get("agent", {}).get("compress_threshold", 65536 * 0.8)
        ),
        "tool_confirmation": tool_confirmation_config,
    }

    tool_manager = ToolManager()

    agent = Agent(
        config=agent_config,
        user_input_queue=user_input_queue,
        user_output_queue=user_output_queue,
        tool_request_queue=tool_request_queue,
        tool_confirmation_queue=tool_confirmation_queue,
        tool_manager=tool_manager,
    )

    return (
        agent,
        user_input_queue,
        user_output_queue,
        tool_request_queue,
        tool_confirmation_queue,
        tool_manager,
    )
