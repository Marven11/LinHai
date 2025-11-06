"""Agent核心模块，负责处理消息、调用工具和管理状态。"""

import json
from pathlib import Path
import datetime
from typing import (
    TypedDict,
    cast,
    NotRequired,
    Sequence,
)

import asyncio
import logging
import traceback
import random
from asyncio import QueueEmpty

from .base import (
    RuntimeMessage,
    DestroyedRuntimeMessage,
    GlobalMemory,
)
from .lifecycle import Lifecycle
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.llm import (
    Message,
    ChatMessage,
    SystemMessage,
    LanguageModel,
    Answer,
    OpenAi,
    OpenAiAnswer,
    ToolCallMessage,
)
from linhai.group_chat import GroupChat
from linhai.type_hints import AgentState
from linhai.config import load_config, ToolConfig, MCPConfig, AgentConfig
from linhai.tool.base import global_tools, ToolSet, ToolArgInfo
from linhai.tool.main import ToolManager
from linhai.tool.mcp_connector import MCPConnector
from linhai.tool.tools.terminal import terminal_toolset
from linhai.prompt import DEFAULT_SYSTEM_PROMPT

from .workflow import compress_history_range
from linhai.input_parser import parse_user_input
from linhai.utils import CliRuntimeNotice, generate_id

logger = logging.getLogger(__name__)


class AgentContext(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    mcp: list[MCPConfig]
    config_basedir: Path
    llms: list[LanguageModel]  # 多个LLM实例
    llm_names: list[str]  # LLM名称列表
    current_llm_index: int  # 当前使用的LLM索引
    compress_threshold_soft: int
    compress_threshold_hard: int
    memory: NotRequired[dict]  # 可选 memory 字段
    tool_confirmation: NotRequired[dict]  # 可选 tool_confirmation 字段


class Agent:
    """Agent核心类，负责处理消息流、调用工具和管理状态机。"""

    def __init__(
        self,
        context: AgentContext,
        group_chat: GroupChat,
        init_messages: Sequence[Message],
    ):
        self.context = context
        self.group_chat = group_chat

        group_chat.register_queue("agent_user_input")
        group_chat.register_member("agent", self)

        self.mcp_connector: MCPConnector | None = None

        self.state: AgentState = "waiting_user"

        self.messages: list[Message] = list(init_messages)

        self.last_token_usage = None
        self.current_enable_compress = True
        self.soft_compress_triggered = False  # 软压缩限制触发标志

        self.large_messages: dict[str, Message] = {}  # 存储大消息的ID映射
        self.queued_messages: list[Message] = []  # 存储/queue消息
        # Plugin使用的变量
        self.compress_tool_called_in_last_response = (
            False  # 记录是否在最近响应中调用了压缩工具
        )
        self.current_disable_waiting_user_warning = False
        
        # 当前Answer实例，用于plugin打断
        self.current_answer: Answer | None = None

        # 生命周期回调管理器
        self.lifecycle = Lifecycle(self.group_chat)

        # 添加LLM切换工具
        llm_toolset = ToolSet()

        # 处理缺少llm_names的情况
        llm_names = self.context.get(
            "llm_names", [f"llm{i}" for i in range(len(self.context["llms"]))]
        )

        @llm_toolset.register_tool(
            name="switch_llm",
            desc="切换到指定的LLM。可用的LLM包括: " + ", ".join(llm_names),
            args={
                "llm_name": ToolArgInfo(desc="要切换到的LLM名称", type="str"),
            },
            required_args=["llm_name"],
        )
        def switch_llm(llm_name: str):
            """切换到指定的LLM

            Args:
                llm_name: 要切换到的LLM名称

            Returns:
                切换结果消息
            """
            if llm_name not in llm_names:
                available_llms = ", ".join(llm_names)
                return f"错误：LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}"

            index = llm_names.index(llm_name)
            self.context["current_llm_index"] = index
            return f"已切换到LLM: {llm_name}"

        @llm_toolset.register_tool(
            name="current_llm",
            desc="显示当前使用的LLM名称",
            args={},
            required_args=[],
        )
        def current_llm():
            """显示当前使用的LLM名称

            Returns:
                当前LLM名称消息
            """
            current_name = llm_names[self.context["current_llm_index"]]
            return f"当前使用的LLM: {current_name}"

        # 确保tool_manager存在
        try:
            tool_manager = self.group_chat.get_members("tool_manager", ToolManager)
        except RuntimeError as e:
            raise RuntimeError("Tool manager must be registered!") from e

        # 将工具集添加到ToolManager
        tool_manager.add_toolset(llm_toolset)

        # 添加虚拟工具集（原dummy.py中的工具）
        dummy_toolset = ToolSet()

        @dummy_toolset.register_tool(
            name="get_token_usage",
            desc="获取token使用情况。",
            args={},
            required_args=[],
        )
        def get_token_usage() -> str:
            """获取token使用情况工具函数。

            Returns:
                str: token使用情况消息
            """
            if self.last_token_usage is not None:
                return f"当前token总用量为: {self.last_token_usage} ({self.last_token_usage/1000:.2f} k)"
            else:
                return "暂无token用量信息"

        @dummy_toolset.register_tool(
            name="thanox_history",
            desc="随机删除一半消息（不包括前5条系统消息）。调用这个工具来触发随机删除流程。",
            args={},
            required_args=[],
        )
        def thanox_history() -> str:
            """随机删除历史消息工具函数。

            Returns:
                str: 删除结果消息
            """
            if len(self.messages) <= 10:
                return "消息数量不足，无需删除"

            indices_to_delete = random.sample(
                range(5, len(self.messages)), len(self.messages) // 2
            )

            self.messages = [
                msg if idx not in indices_to_delete else DestroyedRuntimeMessage()
                for idx, msg in enumerate(self.messages)
            ]

            return f"thanox_history: 随机删除了{len(indices_to_delete)}条消息"

        @dummy_toolset.register_tool(
            name="erase_message_by_uuid",
            desc="擦除通过ID标识的大消息。当工具返回内容过大时，系统会分配ID，你可以调用此工具擦除一些不需要的大消息以节省token。逻辑由从直接删除改为在原位置插入一条runtime message: 本条ID为{ID}的消息已被擦除",
            args={
                "uuids": ToolArgInfo(desc="要擦除的消息的ID", type="list[str]"),
            },
            required_args=["uuids"],
        )
        def erase_message_by_uuid(uuids: list[str]) -> str:
            threshold_info = self.get_threshold_info()
            if threshold_info:
                soft, _hard, used, _remaining, taken = threshold_info
                if used < soft:
                    return "当前token占用没有超过软限制，禁止擦除消息"
                if taken < 0.4:
                    return f"当前token占用小于40%，仅为{taken*100:.2f}%，禁止擦除消息"
            result = ""
            for message_id in uuids:
                result += f"{message_id!r}: {self.erase_message_by_uuid(message_id)}"
            return result

        # 将虚拟工具集添加到ToolManager
        tool_manager.add_toolset(dummy_toolset)

        # 添加workflow工具集（像switch_llm一样）
        workflow_toolset = ToolSet()

        @workflow_toolset.register_tool(
            name="compress_history_range",
            desc="压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
            args={},
            required_args=[],
        )
        async def compress_history_range_tool() -> bool:
            """压缩历史消息工具函数。

            Returns:
                bool: 是否成功执行压缩
            """
            return await compress_history_range(self)

        # 将workflow工具集添加到ToolManager
        tool_manager.add_toolset(workflow_toolset)

        # 解析tool_confirmation配置并存储
        tool_confirmation_config = self.context.get("tool_confirmation", {})
        if not isinstance(tool_confirmation_config, dict):
            tool_confirmation_config = {}
        self.skip_confirmation = tool_confirmation_config.get(
            "skip_confirmation", False
        )
        self.whitelist = tool_confirmation_config.get("whitelist", [])
        self.timeout_seconds = tool_confirmation_config.get("timeout_seconds", 30)

    def get_threshold_info(self) -> tuple[int, int, int, int, float] | None:
        if not self.last_token_usage:
            return None
        compress_threshold_soft = self.context.get(
            "compress_threshold_soft", int(65536 * 0.5)
        )
        compress_threshold_hard = self.context.get(
            "compress_threshold_hard", int(65536 * 0.5)
        )
        taken = (
            0.0
            if self.last_token_usage <= compress_threshold_soft
            else (
                (self.last_token_usage - compress_threshold_soft)
                / (compress_threshold_hard - compress_threshold_soft)
            )
        )
        remaining = compress_threshold_hard - self.last_token_usage
        return (
            compress_threshold_soft,
            compress_threshold_hard,
            self.last_token_usage,
            remaining,
            taken,
        )

    def erase_message_by_uuid(self, message_id: str) -> str:
        """擦除大消息方法。

        Args:
            uuid: 要擦除的消息的ID

        Returns:
            str: 擦除结果消息
        """
        if message_id not in self.large_messages:
            return f"错误：ID '{message_id}' 不存在，无法擦除消息。"

        # 从large_messages中移除
        message_to_delete = self.large_messages[message_id]
        del self.large_messages[message_id]

        # 在原位置插入runtime message而不是直接删除
        if message_to_delete in self.messages:
            index = self.messages.index(message_to_delete)
            self.messages[index] = RuntimeMessage(f"本条ID为{message_id}的消息已被擦除")

        return f"已成功擦除ID为 '{message_id}' 的大消息"

    def interrupt(self, custom_message: str | None = None):
        """
        打断当前Answer并添加自定义消息。
        
        参数:
            custom_message: 自定义消息内容，如果为None则使用默认消息
        """
        if self.current_answer:
            self.current_answer.interrupt()
            if custom_message:
                self.messages.append(RuntimeMessage(custom_message))
            else:
                self.messages.append(RuntimeMessage("Agent被插件打断"))
            self.state = "working"

    async def state_waiting_user(self):
        """
        处理等待用户状态。

        在这个状态下，Agent会等待用户输入消息，然后处理这些消息。
        """
        logger.info("Agent进入等待用户状态")

        if not self.is_last_message_user():
            await self.group_chat.send(
                "cli_runtime_output",
                CliRuntimeNotice(level="INFO", content="Agent正在等待用户"),
            )
            msg = await self.group_chat.receive("agent_user_input")
            assert isinstance(msg, ChatMessage)
            self.handle_user_message(msg)

        await self.generate_response()

    async def state_working(self):
        """
        处理自动运行状态。

        在这个状态下，Agent会自动处理消息并生成响应，
        同时监控token使用量并在需要时触发压缩。
        """
        logger.info("Agent进入自动运行状态")
        # 直接处理用户输入消息
        if not self.group_chat.is_empty("agent_user_input"):
            try:
                msg = await self.group_chat.receive("agent_user_input")
                assert isinstance(msg, ChatMessage)
                self.handle_user_message(msg)
                await self.generate_response()
            except QueueEmpty:
                logger.info("用户输入队列已关闭")
            except RuntimeError as e:
                logger.error("处理消息时出错: %s", str(e))
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

        # 如果最近没有调用压缩工具，才检查软限制并提醒
        if not self.compress_tool_called_in_last_response:
            threshold_info = self.get_threshold_info()
            if threshold_info:
                soft, hard, used, remaining, taken = threshold_info
                if used > soft:
                    self.messages.append(
                        RuntimeMessage(
                            f"当前Token用量为{used}，已达到软限制。硬限制为{hard}，当前使用{taken*100:.1f}%，还有{remaining} token直到强制压缩。"
                            f"当前已有{len(self.messages)}条消息。建议在消息条数少于200条时优先使用 erase_message_by_uuid. "
                        )
                    )

        if self.last_token_usage and self.last_token_usage > self.context.get(
            "compress_threshold_hard", int(65536 * 0.8)
        ):
            # await self.compress()
            await compress_history_range(self)

    async def call_tool(self, tool_call: ToolCallMessage) -> bool:
        """
        直接调用工具并处理结果。

        参数:
            tool_call: 工具调用消息

        返回:
            bool: 是否需要进行早期返回
        """
        if self.state == "waiting_user":
            self.state = "working"

        # 统一设置compress_tool_called_in_last_response
        compress_tools = [
            "compress_history_range",
            "erase_message_by_uuid",
            "thanox_history",
        ]
        self.compress_tool_called_in_last_response = (
            tool_call.function_name in compress_tools
        )

        # 触发工具调用前的生命周期事件
        await self.lifecycle.trigger_before_tool_call(tool_call)

        # 使用存储的tool_confirmation配置（在初始化时解析）
        if self.skip_confirmation or tool_call.function_name in self.whitelist:
            try:
                tool_result = await self.group_chat.get_members(
                    "tool_manager", ToolManager
                ).process_tool_call(tool_call)

                # 检查工具结果，如果是ToolErrorMessage且assert_success为True，则中止
                from linhai.tool.base import ToolErrorMessage

                if (
                    isinstance(tool_result, ToolErrorMessage)
                    and tool_call.assert_success
                ):
                    # 触发工具调用后的生命周期事件（失败）
                    await self.lifecycle.trigger_after_tool_call(
                        tool_call, tool_result, False
                    )
                    msg = f"工具调用失败: {tool_result.content}"
                    logger.error(msg)
                    self.messages.append(RuntimeMessage(msg))
                    return True  # 需要早期返回，中止其他工具调用

                # 触发工具调用后的生命周期事件（成功）
                await self.lifecycle.trigger_after_tool_call(
                    tool_call, tool_result, True
                )

                # 检查工具结果大小，如果大于8000字符则记录ID
                tool_result_content = str(tool_result)
                if len(tool_result_content) > 8000:
                    message_id = generate_id("largemessage")
                    self.large_messages[message_id] = tool_result
                    self.messages.append(
                        RuntimeMessage(
                            f"工具 {tool_call.function_name} 返回的内容较大（{len(tool_result_content)} 字符），已分配ID: {message_id}。"
                            "你可以使用 erase_message_by_uuid 工具删除此消息以节省token。"
                        )
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
                await self.lifecycle.trigger_after_tool_call(tool_call, e, False)

                msg = f"工具调用失败: {str(e)} {repr(e)}"
                logger.error(msg)
                self.messages.append(RuntimeMessage(msg))
                return False

        # 需要用户确认：发送工具请求到队列
        from linhai.cli_ui import CLIApp

        confirmation = await self.group_chat.get_members(
            "cli_app", CLIApp
        ).confirm_tool_request(tool_call)
        self.messages.append(
            RuntimeMessage(
                f"已发送工具调用请求: {tool_call.function_name}，等待用户确认..."
            )
        )

        # 检查确认消息是否匹配当前工具调用
        if confirmation.tool_call.function_name != tool_call.function_name:
            self.messages.append(
                RuntimeMessage("错误：收到的确认消息不匹配当前工具调用")
            )
            return False

        # 根据确认状态执行或取消
        if confirmation.confirmed:
            try:
                tool_result = await self.group_chat.get_members(
                    "tool_manager", ToolManager
                ).process_tool_call(tool_call)
                self.messages.append(
                    RuntimeMessage(f"你调用了工具{tool_call.function_name!r}，结果如下")
                )
                self.messages.append(tool_result)
                return False  # 不需要早期返回
            except (RuntimeError, ValueError, TypeError, OSError, IOError) as e:
                msg = f"工具调用失败: {str(e)} {repr(e)}"
                logger.error(msg)
                self.messages.append(RuntimeMessage(msg))
                return False
        else:
            self.messages.append(
                RuntimeMessage(f"用户取消了工具调用: {tool_call.function_name}")
            )
            return False

    def is_last_message_user(self) -> bool:
        if not self.messages:
            return False
        msg = self.messages[-1]
        return isinstance(msg, ChatMessage) and msg.role == "user"

    def handle_user_message(self, msg: Message):
        """处理并加入用户的消息"""
        assert isinstance(msg, ChatMessage) and msg.role == "user"

        content = msg.message.strip()

        # 使用input_parser解析用户输入
        parsed_input = parse_user_input(content)

        # 处理以@开头的消息（用于切换LLM）
        if parsed_input.switch_model:
            llm_name = parsed_input.switch_model
            if llm_name in self.context["llm_names"]:
                self.context["current_llm_index"] = self.context["llm_names"].index(
                    llm_name
                )
                self.messages.append(
                    RuntimeMessage(f"用户把你的底层LLM切换为了{llm_name!r}")
                )
            else:
                # 添加错误消息
                self.messages.append(
                    RuntimeMessage(
                        f"错误：用户指定的LLM名称{llm_name!r}不存在，请向用户报告这一点"
                    )
                )

        self.messages.append(msg)

    async def _select_model(self) -> LanguageModel:
        """
        根据当前LLM索引选择合适的模型。

        返回:
            LanguageModel: 选择的语言模型实例
        """
        return self.context["llms"][self.context["current_llm_index"]]

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
                    empty_user_msg = RuntimeMessage("继续")
                    self.messages.append(empty_user_msg)

        self.current_enable_compress = enable_compress
        self.current_disable_waiting_user_warning = disable_waiting_user_warning

        # 触发消息生成前的生命周期事件
        await self.lifecycle.trigger_before_message_generation(
            enable_compress, disable_waiting_user_warning
        )

        # 选择模型
        model = await self._select_model()

        answer: Answer = await model.answer_stream(self.messages)
        
        # 设置当前Answer用于plugin打断
        self.current_answer = answer

        # 初始化queued_messages实例变量（如果不存在）
        if not hasattr(self, "queued_messages"):
            self.queued_messages = []

        async for token in answer:
            await self.group_chat.send("cli_agent_output", token)

            # 实时检查工具调用量（通过lifecycle回调处理）
            current_content = answer.get_current_content()

            # 触发消息生成中的生命周期事件
            should_interrupt = await self.lifecycle.trigger_during_message_generation(
                answer, current_content
            )
            if should_interrupt:
                interrupt_msg = CliRuntimeNotice(
                    level="WARNING", content="Agent被插件打断"
                )
                await self.group_chat.send("cli_runtime_output", interrupt_msg)
                return answer

            if not self.group_chat.is_empty("agent_user_input"):
                msg = await self.group_chat.receive("agent_user_input")
                assert isinstance(msg, ChatMessage)
                parsed_input = parse_user_input(msg.message.strip())
                if parsed_input.command == "queue":
                    # 以/queue开头，不打断，将消息添加到排队列表，继续生成响应
                    self.queued_messages.append(msg)
                elif parsed_input.command in ["quit", "exit"]:
                    # 以/quit或/exit开头，直接退出程序
                    await self.group_chat.send("cli_agent_output", answer)
                    chat_message = cast(ChatMessage, answer.get_message())
                    self.messages.append(chat_message)
                    # 发送退出信号
                    await self.group_chat.send("cli_exit", {"return_code": 0})
                    answer.interrupt()
                    return answer
                else:
                    # 正常打断
                    await self.group_chat.send("cli_agent_output", answer)
                    chat_message = cast(ChatMessage, answer.get_message())
                    self.messages.append(chat_message)
                    interrupt_msg = CliRuntimeNotice(
                        level="WARNING", content="Agent被用户打断"
                    )
                    await self.group_chat.send("cli_runtime_output", interrupt_msg)
                    answer.interrupt()
                    self.handle_user_message(msg)
                    return answer

        await self.group_chat.send("cli_agent_output", answer)

        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message
        self.messages.append(chat_message)

        # 将排队消息添加到消息列表，放在agent输出后面
        if self.queued_messages:
            self.messages.append(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            self.messages += self.queued_messages
            self.queued_messages = []  # 清空排队消息

        tool_calls, errors = extract_tool_calls_with_errors(full_response)

        for error in errors:
            self.messages.append(RuntimeMessage(error))

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
            except (RuntimeError, ValueError, TypeError):
                traceback.print_exc()
                continue

        if isinstance(answer, OpenAiAnswer):
            self.last_token_usage = answer.total_tokens

        # 触发消息生成后的生命周期事件
        await self.lifecycle.trigger_after_message_generation(
            answer, full_response, tool_calls
        )

        # 保存对话历史
        await self.save_conversation_history()
        
        # 清除当前Answer引用
        self.current_answer = None
        return answer

    def get_current_llm_info(self) -> tuple[str, LanguageModel]:
        """获取当前LLM的名称和实例。

        返回:
            tuple[str, LanguageModel]: (LLM名称, LLM实例)
        """
        current_index = self.context["current_llm_index"]
        llm_name = self.context["llm_names"][current_index]
        llm_instance = self.context["llms"][current_index]
        return llm_name, llm_instance

    async def save_conversation_history(self):
        """保存对话历史到文件。"""
        history_dir = Path.home() / ".local" / "share" / "linhai" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        # 使用当前时间戳生成文件名
        timestamp = datetime.datetime.now().isoformat().replace(":", "-")
        filename = f"conversation_{timestamp}.json"
        filepath = history_dir / filename

        # 将消息列表转换为JSON可序列化的数据
        history_data = []
        for msg in self.messages:
            # 只保存有to_json方法的消息
            if hasattr(msg, "to_json"):
                try:
                    to_json_result = msg.to_json()
                    # 如果to_json是协程，则await它
                    if asyncio.iscoroutine(to_json_result):
                        to_json_result = await to_json_result
                    msg_dict = json.loads(to_json_result)
                    history_data.append(msg_dict)
                except (TypeError, ValueError, AttributeError):
                    # 如果序列化失败，跳过该消息
                    continue

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            logger.info("对话历史已保存到: %s", filepath)
        except (IOError, OSError) as e:
            logger.error("保存对话历史失败: %s", str(e))

    async def run(self):
        """
        Agent主循环，负责状态机的管理和状态切换。

        根据当前状态调用相应的状态处理函数，
        并处理异常和取消事件。
        """

        # 连接配置中的MCP服务器
        self.mcp_connector = MCPConnector(self.group_chat)
        for mcp_config in self.context["mcp"]:
            server_script_path = self.context["config_basedir"] / mcp_config.server_script_path
            await self.mcp_connector.connect_stdio(
                mcp_config.name, server_script_path.absolute().as_posix()
            )

        logger.info("Agent启动")
        user_input_found = False
        while not self.group_chat.is_empty("agent_user_input"):
            msg = await self.group_chat.receive("agent_user_input")
            self.handle_user_message(msg)
            user_input_found = True
        if user_input_found:
            await self.generate_response()

        while True:
            try:
                if self.state == "waiting_user":
                    await self.state_waiting_user()
                elif self.state == "working":
                    await self.state_working()
                else:
                    logger.error("遇到未知状态: %s，退出运行循环", self.state)
                    break

            except asyncio.CancelledError:
                logger.info("Agent任务被取消")
                break
            await asyncio.sleep(0)


async def create_agent(
    group_chat: GroupChat,
    config_path: str | Path,
    llm_name: str | None = None,
) -> Agent:
    """创建Agent实例

    Args:
        group_chat: GroupChat实例
        config_path: 配置文件路径
        llm_name: 指定的LLM名称（可选）

    Returns:
        Agent实例
    """
    config = load_config(config_path)

    # 创建LLM实例
    llms = await _create_llm_instances(config.llm)

    # 解析tool_confirmation配置
    tool_confirmation_config = {}
    if config.agent and config.agent.tool_confirmation:
        tool_confirmation_config = config.agent.tool_confirmation

    # 创建AgentConfig
    llm_names = [llm_config.name for llm_config in config.llm]
    agent_config = config.agent if config.agent else AgentConfig()
    agent_config = await _create_agent_config(
        llms=llms,
        llm_names=llm_names,
        llm_name=llm_name,
        tool_confirmation_config=tool_confirmation_config,
        agent_config=agent_config,
        mcp_connector_basedir = Path(config_path).parent,
    )

    # 创建ToolManager
    await _create_tool_manager(group_chat, config.tools)

    # 创建初始化消息
    memory_file_path = config.memory.file_path if config.memory else None
    init_messages = await _create_init_messages(
        group_chat=group_chat,
        system_prompt=agent_config["system_prompt"],
        memory_file_path=memory_file_path,
    )

    agent = Agent(
        context=agent_config,
        
        group_chat=group_chat,
        init_messages=init_messages,
    )

    return agent


async def _create_llm_instances(llm_configs: list) -> list[LanguageModel]:
    """创建LLM实例列表

    Args:
        llm_configs: LLM配置列表

    Returns:
        LLM实例列表
    """
    llms = []
    for llm_config in llm_configs:
        llm_config_dict = llm_config.model_dump()
        llm = OpenAi(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            openai_config=llm_config_dict.get("client_options", {}),
            chat_completion_kwargs=llm_config_dict.get("completion_options", {}),
            token_limit=llm_config_dict.get("token_limit"),
            compatibility=llm_config_dict.get("compatibility"),
        )
        llms.append(llm)
    return llms


async def _create_agent_config(
    llms: list[LanguageModel],
    llm_names: list[str],
    llm_name: str | None,
    tool_confirmation_config: dict,
    agent_config: AgentConfig,
    mcp_connector_basedir: Path,
) -> AgentContext:
    """创建AgentConfig字典

    Args:
        llms: LLM实例列表
        llm_names: LLM名称列表
        llm_name: 指定的LLM名称
        tool_confirmation_config: 工具确认配置
        agent_config: Agent配置部分（可选）

    Returns:
        AgentConfig字典
    """
    # 设置压缩阈值
    compress_threshold_hard = int(65536 * 0.8)
    compress_threshold_soft = int(65536 * 0.5)

    if agent_config:
        # 处理compress_threshold_hard
        if isinstance(agent_config.compress_threshold_hard, float):
            compress_threshold_hard = int(
                65536 * agent_config.compress_threshold_hard
            )
        elif isinstance(agent_config.compress_threshold_hard, int):
            compress_threshold_hard = agent_config.compress_threshold_hard
        else:
            raise TypeError("compress_threshold_hard must be int or float")

        # 处理compress_threshold_soft
        if isinstance(agent_config.compress_threshold_soft, float):
            compress_threshold_soft = int(
                65536 * agent_config.compress_threshold_soft
            )
        elif isinstance(agent_config.compress_threshold_soft, int):
            compress_threshold_soft = agent_config.compress_threshold_soft
        else:
            raise TypeError("compress_threshold_soft must be int or float")

    # 处理llm_name参数
    current_llm_index = 0  # 默认使用第一个LLM
    if llm_name is not None:
        if llm_name in llm_names:
            current_llm_index = llm_names.index(llm_name)
        else:
            available_llms = ", ".join(llm_names)
            raise ValueError(
                f"LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}"
            )

    agent_context: AgentContext = {
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "mcp": agent_config.mcp,
        "config_basedir": mcp_connector_basedir,
        "llms": llms,
        "llm_names": llm_names,
        "current_llm_index": current_llm_index,
        "compress_threshold_hard": compress_threshold_hard,
        "compress_threshold_soft": compress_threshold_soft,
        "tool_confirmation": tool_confirmation_config,
    }
    return agent_context


async def _create_tool_manager(group_chat, config: ToolConfig | None):
    """创建ToolManager实例"""
    tool_manager = ToolManager(
        group_chat=group_chat, toolsets=[global_tools, terminal_toolset], config=config
    )
    return tool_manager


async def _create_init_messages(
    group_chat: GroupChat,
    system_prompt: str,
    memory_file_path: str | None = None,
) -> list[Message]:
    """创建初始化消息列表

    Args:
        group_chat: GroupChat实例
        system_prompt: 系统提示语
        memory_file_path: 记忆文件路径（可选）

    Returns:
        初始化消息列表
    """
    init_messages: list[Message] = [
        SystemMessage(
            template=system_prompt,
            current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            group_chat=group_chat,
        )
    ]

    user_global_memory = Path("~/.config/linhai/LINHAI.md").expanduser()
    if memory_file_path:
        user_global_memory = Path(memory_file_path)
    init_messages.append(GlobalMemory(user_global_memory))

    project_memory_filepaths = [
        Path("./LINHAI.md").absolute(),
        Path("./AGENT.md").absolute(),
        Path("./CLAUDE.md").absolute(),
    ]

    for filepath in project_memory_filepaths:
        if filepath.exists():
            init_messages.append(GlobalMemory(filepath))

    return init_messages
