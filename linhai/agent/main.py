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
import random

from .base import (
    RuntimeMessage,
    DestroyedRuntimeMessage,
    GlobalMemory,
)
from .lifecycle import Lifecycle
from .message import AgentMessage
from .toolcall import AgentToolcall
from linhai.markdown_parser import extract_tool_calls_with_errors, ParseError
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
    llms: list[LanguageModel]  # 多个LLM实例
    llm_names: list[str]  # LLM名称列表
    current_llm_index: int  # 当前使用的LLM索引
    compress_threshold_soft: int | float
    compress_threshold_hard: int | float
    memory: NotRequired[dict]  # 可选 memory 字段
    tool_confirmation: NotRequired[dict]  # 可选 tool_confirmation 字段
    enable_directory_change_detection: NotRequired[bool]  # 是否启用目录更改检测


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

        # 使用AgentMessage类管理消息
        self.message_processor = AgentMessage(init_messages)
        self.toolcall_processor = AgentToolcall(self)

        self.last_token_usage = None
        self.current_enable_compress = True
        self.soft_compress_triggered = False  # 软压缩限制触发标志
        self.large_messages = {}  # 大消息存储

        # Plugin使用的变量
        self.compress_tool_called_in_last_response = (
            False  # 记录是否在最近响应中调用了压缩工具
        )
        self.current_disable_waiting_user_warning = False

        self.last_threshold_state = None  # 用于跟踪上次的阈值状态

        # 当前Answer实例，用于plugin打断
        self.current_answer: Answer | None = None

        # 生命周期回调管理器
        self.lifecycle = Lifecycle(self.group_chat)

        # 为兼容性添加messages属性，代理到message_processor
        self.messages = self.message_processor.get_messages()

    def erase_message_by_id(self, message_id: str) -> str:
        """擦除大消息。
        
        Args:
            message_id: 要擦除的消息ID
            
        Returns:
             擦除结果消息
        """
        return self.message_processor.erase_message_by_id(message_id)

        self.last_token_usage = None
        self.current_enable_compress = True
        self.soft_compress_triggered = False  # 软压缩限制触发标志
        self.large_messages = {}  # 大消息存储

        # Plugin使用的变量
        self.compress_tool_called_in_last_response = (
            False  # 记录是否在最近响应中调用了压缩工具
        )
        self.current_disable_waiting_user_warning = False

        # 当前Answer实例，用于plugin打断
        self.current_answer: Answer | None = None

        # 生命周期回调管理器
        self.lifecycle = Lifecycle(self.group_chat)

    def get_threshold_info(self) -> tuple[int, int, int, int, float] | None:
        if not self.last_token_usage:
            return None
        
        # 获取当前LLM的token_limit
        current_llm = self.context["llms"][self.context["current_llm_index"]]
        token_limit = getattr(current_llm, 'token_limit', 65536)
        
        # 动态计算阈值：如果是float则乘以token_limit，如果是int则直接使用
        soft_config = self.context.get("compress_threshold_soft", 0.5)
        hard_config = self.context.get("compress_threshold_hard", 0.8)
        
        compress_threshold_soft = int(soft_config * token_limit) if isinstance(soft_config, float) else soft_config
        compress_threshold_hard = int(hard_config * token_limit) if isinstance(hard_config, float) else hard_config
        
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




    async def interrupt(self, custom_message: str | None = None):
        """
        打断当前Answer并添加自定义消息。

        参数:
            custom_message: 自定义消息内容，如果为None则使用默认消息
        """
        if self.current_answer:
            self.current_answer.interrupt()
            await self.group_chat.send("cli_agent_output", self.current_answer)
            self.current_answer = None
            
            # 发送插件打断消息到运行时输出
            if custom_message:
                interrupt_msg = CliRuntimeNotice(
                    level="WARNING", content=custom_message
                )
                self.message_processor.append_message(RuntimeMessage(custom_message))
            else:
                interrupt_msg = CliRuntimeNotice(
                    level="WARNING", content="Agent被打断"
                )
                self.message_processor.append_message(RuntimeMessage("Agent被打断"))
            
            await self.group_chat.send("cli_runtime_output", interrupt_msg)
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
            except RuntimeError as e:
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

        # 如果最近没有调用压缩工具，才检查软限制并提醒
        if not self.compress_tool_called_in_last_response:
            threshold_info = self.get_threshold_info()
            if threshold_info:
                self.message_processor.add_soft_threshold_notification(
                    threshold_info, self.large_messages, self.compress_tool_called_in_last_response
                )

        if self.last_token_usage and self.last_token_usage > self.context.get(
            "compress_threshold_hard", int(65536 * 0.8)
        ):
            # await self.compress()
            await compress_history_range(self)



    def is_last_message_user(self) -> bool:
        if not self.message_processor.get_messages():
            return False
        msg = self.message_processor.get_messages()[-1]
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
                self.message_processor.append_message(
                    RuntimeMessage(f"用户把你的底层LLM切换为了{llm_name!r}")
                )
            else:
                # 添加错误消息
                self.message_processor.append_message(
                    RuntimeMessage(
                        f"错误：用户指定的LLM名称{llm_name!r}不存在，请向用户报告这一点"
                    )
                )

        self.message_processor.append_message(msg)

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
        if self.message_processor.get_message_count() > 0:
            last_msg = self.message_processor.get_messages()[-1]
            if isinstance(last_msg, ChatMessage):
                llm_msg = last_msg.to_llm_message()
                if llm_msg.get("role") == "assistant":
                    empty_user_msg = RuntimeMessage("继续")
                    self.message_processor.append_message(empty_user_msg)

        self.current_enable_compress = enable_compress
        self.current_disable_waiting_user_warning = disable_waiting_user_warning

        # 触发消息生成前的生命周期事件
        await self.lifecycle.trigger_before_message_generation(
            enable_compress, disable_waiting_user_warning
        )

        # 选择模型
        model = await self._select_model()

        answer: Answer = await model.answer_stream(self.message_processor.get_messages())

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
            interrupted = await self.lifecycle.trigger_during_message_generation(
                answer, current_content
            )
            if interrupted:
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
                    self.message_processor.append_message(chat_message)
                    # 发送退出信号
                    await self.group_chat.send("cli_exit", {"return_code": 0})
                    answer.interrupt()
                    return answer
                else:
                    # 正常打断
                    await self.group_chat.send("cli_agent_output", answer)
                    chat_message = cast(ChatMessage, answer.get_message())
                    self.message_processor.append_message(chat_message)
                    await self.interrupt("Agent被用户打断")
                    self.handle_user_message(msg)
                    return answer

        await self.group_chat.send("cli_agent_output", answer)

        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message
        self.message_processor.append_message(chat_message)

        # 将排队消息添加到消息列表，放在agent输出后面
        if self.queued_messages:
            self.message_processor.append_message(
                RuntimeMessage("用户在你回答的时候输出了以下排队消息，现在请处理：")
            )
            self.message_processor.get_messages().extend(self.queued_messages)
            self.queued_messages = []  # 清空排队消息

        try:
            tool_calls, errors = extract_tool_calls_with_errors(full_response)
        except ParseError:
            # 正常打断
            interrupt_msg = CliRuntimeNotice(
                level="WARNING", content="工具调用格式出错"
            )
            await self.group_chat.send("cli_runtime_output", interrupt_msg)
            return answer

        for error in errors:
            self.message_processor.append_message(RuntimeMessage(error))

        for call in tool_calls:
            if "name" in call and "arguments" in call:
                tool_call = ToolCallMessage(
                    function_name=call["name"],
                    function_arguments=call["arguments"],
                )
                early_return = await self.call_tool(tool_call)
                if early_return:
                    return await self.generate_response()

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

    async def call_tool(self, tool_call):
        """调用工具，委托给toolcall_processor处理。
        
        Args:
            tool_call: 工具调用消息
            
        Returns:
            bool: 是否需要进行早期返回
        """
        return await self.toolcall_processor.call_tool(tool_call)

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
        for msg in self.message_processor.get_messages():
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
                break
            await asyncio.sleep(0)

        # 只有在MCP连接器存在时才断开连接
        if self.group_chat.has_member("mcp_connector"):
            await self.group_chat.get_members("mcp_connector", MCPConnector).disconnect_all()

async def create_agent(
    group_chat: GroupChat,
    config_path: Path,
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
    agent_context = await _create_agent_context(
        llms=llms,
        llm_names=llm_names,
        llm_name=llm_name,
        tool_confirmation_config=tool_confirmation_config,
        agent_config=agent_config,
    )

    # 创建ToolManager
    tool_config = config.tools if config.tools else ToolConfig()
    await _create_tool_manager(group_chat, tool_config, agent_config.mcp, mcp_basedir=config_path.parent)

    # 创建初始化消息
    memory_file_path = (config_path.parent / config.memory.file_path) if config.memory else None
    init_messages = await _create_init_messages(
        group_chat=group_chat,
        system_prompt=agent_context["system_prompt"],
        memory_file_path=memory_file_path,
    )

    agent = Agent(
        context=agent_context,
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


async def _create_agent_context(
    llms: list[LanguageModel],
    llm_names: list[str],
    llm_name: str | None,
    tool_confirmation_config: dict,
    agent_config: AgentConfig,
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
    # 设置压缩阈值（存储原始配置值，将在运行时根据当前LLM动态计算）
    compress_threshold_hard: int | float = 0.8  # 默认硬阈值比例
    compress_threshold_soft: int | float = 0.5  # 默认软阈值比例

    if agent_config:
        # 存储原始配置值，不转换为绝对token数
        compress_threshold_hard = agent_config.compress_threshold_hard
        compress_threshold_soft = agent_config.compress_threshold_soft

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
        "llms": llms,
        "llm_names": llm_names,
        "current_llm_index": current_llm_index,
        "compress_threshold_hard": compress_threshold_hard,
        "compress_threshold_soft": compress_threshold_soft,
        "tool_confirmation": tool_confirmation_config,
        "enable_directory_change_detection": agent_config.enable_directory_change_detection if agent_config else False,
    }
    return agent_context


async def _create_tool_manager(group_chat, config: ToolConfig, mcp_config: list[MCPConfig], mcp_basedir: Path):
    """创建ToolManager实例"""
    tool_manager = ToolManager(
        group_chat=group_chat, toolsets=[global_tools, terminal_toolset], config=config, mcp_config =mcp_config, mcp_basedir=mcp_basedir
    )
    return tool_manager


async def _create_init_messages(
    group_chat: GroupChat,
    system_prompt: str,
    memory_file_path: Path | None = None,
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

    user_global_memory = memory_file_path.absolute() if memory_file_path else Path("~/.config/linhai/LINHAI.md").expanduser()
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
