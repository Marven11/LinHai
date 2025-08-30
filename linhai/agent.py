"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

from pathlib import Path
from typing import TypedDict, cast, NotRequired, Callable, Awaitable, Any
from reprlib import Repr
import asyncio
import logging
import json
import traceback
import datetime
import random
from asyncio import Queue, QueueEmpty

from linhai.agent_base import (
    RuntimeMessage,
    CompressRequest,
    DestroyedRuntimeMessage,
)
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
from linhai.type_hints import AgentState
from linhai.config import load_config
from linhai.tool.main import ToolManager
from linhai.tool.base import get_tools_info
from linhai.prompt import DEFAULT_SYSTEM_PROMPT, COMPRESS_RANGE_PROMPT
from linhai.agent_plugin import register_default_plugins

logger = logging.getLogger(__name__)

repr_obj = Repr(maxstring=100)


class AgentConfig(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    model: LanguageModel
    compress_threshold_soft: int
    compress_threshold_hard: int
    memory: NotRequired[dict]  # 可选 memory 字段
    tool_confirmation: NotRequired[dict]  # 可选 tool_confirmation 字段
    cheap_model: NotRequired[LanguageModel]  # 可选廉价LLM字段


class GlobalMemory:
    """全局记忆类，用于读取和呈现全局记忆文件内容。"""

    # pylint: disable=too-few-public-methods

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将全局记忆转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含全局记忆内容的系统消息
        """
        try:
            content = self.filepath.read_text()
            return {
                "role": "system",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，内容如下

{content}
""",
            }
        except FileNotFoundError:
            return {
                "role": "system",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，但文件不存在或已被移动/删除
""",
            }
        except (IOError, OSError) as e:
            return {
                "role": "system",
                "content": f"""
# 全局记忆

文件位于{self.filepath.as_posix()!r}，读取时发生错误: {str(e)}
""",
            }


# 生命周期回调类型定义
from typing import TypeAlias

BeforeMessageGenerationCallback: TypeAlias = Callable[
    ["Agent", bool, bool],  # agent, enable_compress, disable_waiting_user_warning
    Awaitable[None],
]

AfterMessageGenerationCallback: TypeAlias = Callable[
    ["Agent", Answer, str, list[dict]],  # agent, answer, full_response, tool_calls
    Awaitable[None],
]

BeforeToolCallCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage], Awaitable[None]  # agent, tool_call
]

AfterToolCallCallback: TypeAlias = Callable[
    ["Agent", ToolCallMessage, Any, bool],  # agent, tool_call, tool_result, success
    Awaitable[None],
]


class Lifecycle:
    """生命周期回调管理器，使用明确的参数传递。"""

    def __init__(self):
        self._before_message_generation_callbacks: list[
            BeforeMessageGenerationCallback
        ] = []
        self._after_message_generation_callbacks: list[
            AfterMessageGenerationCallback
        ] = []
        self._before_tool_call_callbacks: list[BeforeToolCallCallback] = []
        self._after_tool_call_callbacks: list[AfterToolCallCallback] = []

    def register_before_message_generation(
        self, callback: BeforeMessageGenerationCallback
    ):
        """注册消息生成前的回调。"""
        self._before_message_generation_callbacks.append(callback)

    def register_after_message_generation(
        self, callback: AfterMessageGenerationCallback
    ):
        """注册消息生成后的回调。"""
        self._after_message_generation_callbacks.append(callback)

    def register_before_tool_call(self, callback: BeforeToolCallCallback):
        """注册工具调用前的回调。"""
        self._before_tool_call_callbacks.append(callback)

    def register_after_tool_call(self, callback: AfterToolCallCallback):
        """注册工具调用后的回调。"""
        self._after_tool_call_callbacks.append(callback)

    async def trigger_before_message_generation(
        self, agent: "Agent", enable_compress: bool, disable_waiting_user_warning: bool
    ):
        """触发消息生成前的事件。"""
        for callback in self._before_message_generation_callbacks:
            try:
                await callback(agent, enable_compress, disable_waiting_user_warning)
            except Exception as e:
                logger.error("Before message generation callback error: %s", e)

    async def trigger_after_message_generation(
        self, agent: "Agent", answer: Answer, full_response: str, tool_calls: list[dict]
    ):
        """触发消息生成后的事件。"""
        for callback in self._after_message_generation_callbacks:
            try:
                await callback(agent, answer, full_response, tool_calls)
            except Exception as e:
                logger.error("After message generation callback error: %s", e)

    async def trigger_before_tool_call(
        self, agent: "Agent", tool_call: ToolCallMessage
    ):
        """触发工具调用前的事件。"""
        for callback in self._before_tool_call_callbacks:
            try:
                await callback(agent, tool_call)
            except Exception as e:
                logger.error("Before tool call callback error: %s", e)

    async def trigger_after_tool_call(
        self,
        agent: "Agent",
        tool_call: ToolCallMessage,
        tool_result: Any,
        success: bool,
    ):
        """触发工具调用后的事件。"""
        for callback in self._after_tool_call_callbacks:
            try:
                await callback(agent, tool_call, tool_result, success)
            except Exception as e:
                logger.error("After tool call callback error: %s", e)


class Agent:
    """Agent核心类，负责处理消息流、调用工具和管理状态机。"""

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
        self.soft_compress_triggered = False  # 软压缩限制触发标志

        # 廉价LLM状态跟踪
        self.cheap_llm_remaining_messages = 0

        # Plugin使用的变量
        self.current_disable_waiting_user_warning = False

        # 生命周期回调管理器
        self.lifecycle = Lifecycle()
        # 注册默认Plugin
        register_default_plugins(self.lifecycle)

        # 加载全局记忆
        memory_config = config.get("memory", {})
        memory_filepath = Path(memory_config.get("file_path", "./LINHAI.md")).absolute()
        self.messages.append(
            GlobalMemory(memory_filepath)
        )  # 总是添加，无论文件是否存在

        # 解析tool_confirmation配置并存储
        tool_confirmation_config = self.config.get("tool_confirmation", {})
        self.skip_confirmation = tool_confirmation_config.get(
            "skip_confirmation", False
        )
        self.whitelist = tool_confirmation_config.get("whitelist", [])
        self.timeout_seconds = tool_confirmation_config.get("timeout_seconds", 30)

    async def state_waiting_user(self):
        """
        处理等待用户状态。

        在这个状态下，Agent会等待用户输入消息，然后处理这些消息。
        """
        logger.info("Agent进入等待用户状态")
        while self.state == "waiting_user":
            chat_msg = await self.user_input_queue.get()
            if chat_msg is None:
                break

            await self.handle_messages([chat_msg])

    async def state_working(self):
        """
        处理自动运行状态。

        在这个状态下，Agent会自动处理消息并生成响应，
        同时监控token使用量并在需要时触发压缩。
        """
        logger.info("Agent进入自动运行状态")
        # 直接处理用户输入消息
        if not self.user_input_queue.empty():
            try:
                msg = await self.user_input_queue.get()
                await self.handle_messages([cast(ChatMessage, msg)])
            except QueueEmpty:
                logger.info("用户输入队列已关闭")
            except (QueueEmpty, RuntimeError) as e:
                logger.error("处理消息时出错: %s", str(e))
                self.state = "paused"
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

        if self.last_token_usage and self.last_token_usage > self.config.get(
            "compress_threshold_soft", int(65536 * 0.5)
        ):
            self.messages.append(
                RuntimeMessage(
                    f"现在的Token用量为{self.last_token_usage}，做完这个步骤就压缩历史吧"
                )
            )

        if self.last_token_usage and self.last_token_usage > self.config.get(
            "compress_threshold_hard", int(65536 * 0.8)
        ):
            # await self.compress()
            await self.thanox_history()

    async def state_paused(self):
        """
        处理暂停运行状态。

        在这个状态下，Agent会等待用户输入来恢复运行，
        通常用于处理错误或异常情况后的恢复。
        """
        logger.info("Agent进入暂停运行状态")
        try:
            msg = await self.user_input_queue.get()
            self.state = "waiting_user"
            await self.handle_messages([cast(ChatMessage, msg)])
        except QueueEmpty:
            logger.info("用户输入队列已关闭")
        except (RuntimeError, asyncio.CancelledError) as e:
            logger.error("处理消息时出错: %s", str(e))
            raise RuntimeError("处理消息时出错") from e

    async def compress(self):
        """
        压缩历史消息以减少上下文长度。

        通过请求LLM对历史消息进行评分，然后删除评分较低的消息
        来减少上下文长度，从而节省token使用量。
        """
        messages = [msg.to_llm_message() for msg in self.messages]
        messages_summerization = "\n".join(
            f"- id: {i} role: {msg["role"]!r} content: {repr_obj.repr(msg.get('content', None))}"
            for i, msg in enumerate(messages)
        )
        self.messages.append(CompressRequest(messages_summerization))

        # 保存当前廉价LLM状态
        original_cheap_remaining = self.cheap_llm_remaining_messages
        # 如果廉价LLM可用，设置为使用1个消息进行压缩
        if "cheap_model" in self.config:
            self.cheap_llm_remaining_messages = 1

        answer = await self.generate_response(
            enable_compress=False, disable_waiting_user_warning=True
        )
        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message
        # 恢复廉价LLM状态
        self.cheap_llm_remaining_messages = original_cheap_remaining
        try:
            scores_data = extract_json_blocks(full_response)
            if len(scores_data) == 0:
                self.messages.append(
                    RuntimeMessage(
                        "错误：没有检测到json block，请确保输出包含正确的json格式评分数据"
                    )
                )
                return
            if len(scores_data) != 1:
                self.messages.append(
                    RuntimeMessage("数据数量有误，你应该重新开启压缩历史流程")
                )
                return
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
                RuntimeMessage(
                    f"压缩已经完成，消息数量从{original_count}条减少到{compressed_count}条，"
                    f"减少了{original_count - compressed_count}条消息"
                )
            )
        except LLMResponseError as exc:
            self.messages.append(
                RuntimeMessage(
                    f"错误：你没有输出需要的score，请调用工具重新启动流程: {exc!r}"
                )
            )
        except Exception as exc:
            self.messages.append(RuntimeMessage(f"错误：{exc!r}"))

    async def thanox_history(self):
        """随机删除一半消息（不包括前5条系统消息）"""
        if len(self.messages) <= 10:
            return

        indices_to_delete = random.sample(
            range(5, len(self.messages)), len(self.messages) // 2
        )

        self.messages = [
            msg if idx not in indices_to_delete else DestroyedRuntimeMessage()
            for idx, msg in enumerate(self.messages)
        ]

        self.messages.append(
            RuntimeMessage(f"thanox_history: 随机删除了{len(indices_to_delete)}条消息")
        )

    async def compress_range(self):
        """
        压缩指定范围的历史消息以减少上下文长度。

        通过提示LLM输出要压缩的消息范围（start_id和end_id），
        然后删除指定范围内的消息。
        """
        messages = [msg.to_llm_message() for msg in self.messages]
        messages_summerization = "\n".join(
            f"- id: {i} role: {msg["role"]!r} content: {repr_obj.repr(msg.get('content', None))}"
            for i, msg in enumerate(messages)
        )
        self.messages.append(
            RuntimeMessage(
                COMPRESS_RANGE_PROMPT.replace(
                    "{|SUMMERIZATION|}", messages_summerization
                )
            )
        )

        # 保存当前廉价LLM状态
        original_cheap_remaining = self.cheap_llm_remaining_messages
        # 如果廉价LLM可用，设置为使用1个消息进行压缩
        if "cheap_model" in self.config:
            self.cheap_llm_remaining_messages = 1

        # 生成响应，让LLM输出范围
        answer = await self.generate_response(
            enable_compress=False, disable_waiting_user_warning=True
        )
        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message
        # 恢复廉价LLM状态
        self.cheap_llm_remaining_messages = original_cheap_remaining

        try:
            # 解析LLM输出，提取JSON块
            json_blocks = extract_json_blocks(full_response)
            if len(json_blocks) == 0:
                self.messages.append(
                    RuntimeMessage(
                        "错误：没有检测到JSON block，请确保输出包含正确的JSON格式范围数据"
                    )
                )
                return

            # 提取第一个JSON块
            range_data = json_blocks[0]
            if not isinstance(range_data, dict):
                self.messages.append(
                    RuntimeMessage("错误：JSON block 格式不正确，应为字典")
                )
                return

            start_id = range_data.get("start_id")
            end_id = range_data.get("end_id")

            if start_id is None or end_id is None:
                self.messages.append(
                    RuntimeMessage("错误：JSON block 必须包含 start_id 和 end_id 字段")
                )
                return

            # 验证参数类型
            if not isinstance(start_id, int) or not isinstance(end_id, int):
                self.messages.append(
                    RuntimeMessage("错误：start_id 和 end_id 必须为整数")
                )
                return

            # 参数验证
            if start_id < 0 or end_id < 0:
                self.messages.append(RuntimeMessage("错误：消息ID不能为负数"))
                return

            if start_id > end_id:
                self.messages.append(RuntimeMessage("错误：起始ID不能大于结束ID"))
                return

            # 确保不删除前5条系统消息
            if start_id <= 5:
                self.messages.append(RuntimeMessage("错误：不能删除前5条系统消息"))
                return

            # 检查范围大小，至少10条消息
            range_size = end_id - start_id + 1
            if range_size < 10:
                self.messages.append(RuntimeMessage("错误：压缩范围至少需要10条消息"))
                return

            # 检查范围是否有效
            if end_id >= len(self.messages):
                self.messages.append(RuntimeMessage("错误：结束ID超出消息范围"))
                return

            # 直接删除指定范围的消息
            del self.messages[start_id : end_id + 1]

            # 报告压缩统计
            self.messages.append(
                RuntimeMessage(
                    f"范围压缩已完成，删除了{range_size}条消息（从{start_id}到{end_id}）"
                )
            )
        except Exception as exc:
            self.messages.append(
                RuntimeMessage(f"错误：处理压缩范围时发生异常: {str(exc)}")
            )

    async def call_tool(self, tool_call: ToolCallMessage) -> bool:
        """
        直接调用工具并处理结果。

        参数:
            tool_call: 工具调用消息

        返回:
            bool: 是否需要进行早期返回
        """
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

        if tool_call.function_name == "compress_history_range":
            if self.current_enable_compress:
                await self.compress_range()
            else:
                self.messages.append(
                    RuntimeMessage(
                        "当前禁止调用compress_history_range工具，你是不是弄错什么了？"
                    )
                )
            return True

        if tool_call.function_name == "thanox_history":
            await self.thanox_history()
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

        if tool_call.function_name == "switch_to_cheap_llm":
            # 检查廉价LLM是否可用
            if "cheap_model" not in self.config:
                self.messages.append(
                    RuntimeMessage("错误：廉价LLM未配置，无法启用廉价LLM模式")
                )
                return False

            # 解析参数
            try:
                args = tool_call.function_arguments  # 现在直接是字典，无需解析
                message_count = args.get("message_count", 1)

                if message_count <= 0:
                    self.messages.append(RuntimeMessage("错误：消息数量必须大于0"))
                    return False

                # 添加消息数量限制，最多5个消息
                if message_count > 5:
                    self.messages.append(
                        RuntimeMessage("错误：廉价LLM最多只能使用5个消息")
                    )
                    return False

                self.cheap_llm_remaining_messages = message_count

                self.messages.append(
                    RuntimeMessage(
                        f"已切换到廉价LLM模式，将在接下来的{message_count}条消息中使用廉价LLM。请在规划中列出所有需要读取的文件和列出的文件夹。"
                    )
                )
                return False
            except (TypeError, AttributeError):
                self.messages.append(RuntimeMessage("错误：工具参数格式不正确"))
                return False

        # 检查如果是read_file工具且没有使用廉价LLM，提醒agent
        if (
            tool_call.function_name == "read_file"
            and self.cheap_llm_remaining_messages == 0
        ):
            self.messages.append(
                RuntimeMessage("提醒：读取多个文件时建议使用廉价LLM以节省成本。")
            )

        # 廉价LLM模式下限制工具调用：只允许读取相关工具
        if self.cheap_llm_remaining_messages > 0:
            allowed_tools = {
                "read_file",
                "list_files",
                "get_absolute_path",
                "get_token_usage",
            }
            if tool_call.function_name not in allowed_tools:
                # 自动切换回普通LLM
                self.cheap_llm_remaining_messages = 0
                self.messages.append(
                    RuntimeMessage(
                        f"错误：廉价LLM模式下不允许调用{tool_call.function_name!r}工具。"
                        "已自动切换回普通LLM模式。廉价LLM只能用于读取文件、"
                        "查看目录和获取信息。"
                    )
                )
                self.messages.append(RuntimeMessage("廉价LLM已经结束，现在你是普通LLM"))
                return False

        # 触发工具调用前的生命周期事件
        await self.lifecycle.trigger_before_tool_call(self, tool_call)

        # 使用存储的tool_confirmation配置（在初始化时解析）
        if self.skip_confirmation or tool_call.function_name in self.whitelist:
            try:
                tool_result = await self.tool_manager.process_tool_call(tool_call)
                # 触发工具调用后的生命周期事件（成功）
                await self.lifecycle.trigger_after_tool_call(
                    self, tool_call, tool_result, True
                )

                self.messages.append(
                    RuntimeMessage(f"你调用了工具{tool_call.function_name!r}，结果如下")
                )
                self.messages.append(tool_result)
                if self.state == "waiting_user":
                    self.state = "working"
                return False  # 不需要早期返回
            except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:
                # 触发工具调用后的生命周期事件（失败）
                await self.lifecycle.trigger_after_tool_call(self, tool_call, e, False)

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
            except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:
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
        """
        处理新的消息并将其添加到消息历史中。

        参数:
            messages: 要处理的消息列表

        返回:
            生成的响应
        """
        self.messages += messages
        try:
            return await self.generate_response()
        except Exception:
            self.state = "paused"
            raise

    async def _select_model(self) -> LanguageModel:
        """
        根据廉价LLM剩余消息计数选择合适的模型。

        返回:
            LanguageModel: 选择的语言模型实例
        """
        if self.cheap_llm_remaining_messages > 0 and "cheap_model" in self.config:
            return self.config["cheap_model"]
        return self.config["model"]

    async def generate_response(
        self, enable_compress: bool = True, disable_waiting_user_warning: bool = False
    ) -> Answer:
        """
        生成回复并发送给用户。

        参数:
            enable_compress: 是否启用压缩功能
            disable_waiting_user_warning: 是否禁用等待用户警告

        返回:
            Answer: 生成的回答对象
        """
        # Check if the last message is from assistant, add empty user message if so
        if len(self.messages) > 0:
            last_msg = self.messages[-1]
            if isinstance(last_msg, ChatMessage):
                llm_msg = last_msg.to_llm_message()
                if llm_msg.get("role") == "assistant":
                    empty_user_msg = ChatMessage(role="user", message="")
                    self.messages.append(empty_user_msg)

        self.current_enable_compress = enable_compress
        self.current_disable_waiting_user_warning = disable_waiting_user_warning

        # 触发消息生成前的生命周期事件
        await self.lifecycle.trigger_before_message_generation(
            self, enable_compress, disable_waiting_user_warning
        )

        # 选择模型
        model = await self._select_model()

        answer: Answer = await model.answer_stream(self.messages)

        async for token in answer:
            await self.user_output_queue.put(token)

            # Real-time check for too many tool calls
            current_content = answer.get_current_content()
            json_block_count = current_content.count("\n```json")

            # 基于回答长度动态调整JSON块限制
            content_length = len(current_content)
            if content_length < 1000:  # 小于1000字符，允许最多5个工具调用
                max_json_blocks = 5
            else:  # 大于等于1000字符，只允许1个工具调用
                max_json_blocks = 1

            if json_block_count > max_json_blocks:
                await self.user_output_queue.put(answer)
                self.messages.append(
                    RuntimeMessage(f"错误：一次性调用了超过{max_json_blocks}个工具，当前回答长度{content_length}字符，最多允许{max_json_blocks}个工具调用。请分多次调用。")
                )
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
                        function_arguments=call["arguments"],
                    )
                    early_return = await self.call_tool(tool_call)
                    if early_return:
                        return await self.generate_response()
            except Exception:
                traceback.print_exc()
                continue

        # 减少廉价LLM剩余消息计数
        if self.cheap_llm_remaining_messages > 0:
            self.cheap_llm_remaining_messages -= 1
            if self.cheap_llm_remaining_messages == 0:
                self.messages.append(RuntimeMessage("廉价LLM已经结束，现在你是普通LLM"))

        if isinstance(answer, OpenAiAnswer):
            self.last_token_usage = answer.total_tokens

        # 触发消息生成后的生命周期事件
        await self.lifecycle.trigger_after_message_generation(
            self, answer, full_response, tool_calls
        )

        return answer

    async def run(self):
        """
        Agent主循环，负责状态机的管理和状态切换。

        根据当前状态调用相应的状态处理函数，
        并处理异常和取消事件。
        """
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
            # 感觉pause不应该存在，至少不应该这么用
            # except Exception as e:
            #     logger.error("Agent运行出错: %s", str(e))
            #     self.messages.append(
            #         RuntimeMessage(f"Agent运行出错: {str(e)} {repr(e)}")
            #     )
            #     self.state = "paused"
            #     raise RuntimeError("Agent运行出错") from e
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

    # 加载廉价LLM配置
    cheap_llm = None
    if "cheap" in config["llm"]:
        cheap_llm = OpenAi(
            api_key=config["llm"]["cheap"]["api_key"],
            base_url=config["llm"]["cheap"]["base_url"],
            model=config["llm"]["cheap"]["model"],
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

    agent_config: AgentConfig = {
        "system_prompt": system_prompt,
        "model": llm,
        "compress_threshold_hard": int(
            config_dict.get("agent", {}).get("compress_threshold_hard", 65536 * 0.8)
        ),
        "compress_threshold_soft": int(
            config_dict.get("agent", {}).get("compress_threshold_soft", 65536 * 0.5)
        ),
        "tool_confirmation": tool_confirmation_config,
    }
    if cheap_llm:
        agent_config["cheap_model"] = cheap_llm

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
