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

from linhai.agent_base import (
    RuntimeMessage,
    DestroyedRuntimeMessage,
    GlobalMemory,
)
from linhai.agent_lifecycle import Lifecycle
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
    LanguageModelMessage,
)
from linhai.group_chat import GroupChat
from linhai.type_hints import AgentState
from linhai.config import load_config
from linhai.tool.base import global_tools, ToolSet, ToolArgInfo
from linhai.tool.main import ToolManager
from linhai.prompt import DEFAULT_SYSTEM_PROMPT
from linhai.agent_plugin import register_default_plugins
from linhai.agent_workflow import compress_history_range

import linhai

logger = logging.getLogger(__name__)


class AgentConfig(TypedDict):
    """Agent配置参数"""

    system_prompt: str
    llms: list[LanguageModel]  # 多个LLM实例
    llm_names: list[str]  # LLM名称列表
    current_llm_index: int  # 当前使用的LLM索引
    compress_threshold_soft: int
    compress_threshold_hard: int
    memory: NotRequired[dict]  # 可选 memory 字段
    tool_confirmation: NotRequired[dict]  # 可选 tool_confirmation 字段


class CheapLlmStatusMessage:
    """廉价LLM状态消息类，用于显示廉价LLM模式的可用性。"""

    # pylint: disable=too-few-public-methods

    def __init__(self, is_cheap_llm_available: bool):
        self.is_cheap_llm_available = is_cheap_llm_available

    def to_llm_message(self) -> LanguageModelMessage:
        """
        将廉价LLM状态转换为LLM消息格式。

        返回:
            LanguageModelMessage: 包含廉价LLM状态和规则的系统消息
        """
        if self.is_cheap_llm_available:
            status = "廉价LLM模式可用，请积极使用廉价LLM"
            intro = """
有时需要探索文件内容时可以使用廉价LLM完成，以减少成本。

因为廉价LLM能力较差，运行时会禁止廉价LLM使用部分工具，因此廉价LLM不能也不应该
  - 执行命令
  - 写文件
  - 调用其他修改当前环境的工具
"""
            rules = """
## ACTION RULES - CHEAP LLM USAGE

- 积极使用廉价LLM模式读取文件、查看代码和获取信息，以节省成本
- 根据以下规则判断是否需要使用廉价LLM
  - 多文件读取：如果需要读取多个内容(文件内容/文件夹内容/...)且已知目标位置，则直接调用多个工具，不需要使用廉价LLM
  - 项目探索：如果需要读取多个内容(文件内容/文件夹内容/...)但目标位置未知，则需要使用廉价LLM
  - 项目探索：如果需要读取内容，根据内容的结果探索更多内容（如读取文档并根据文档行动），则需要使用廉价LLM
  - 修改文件：如果需要执行修改文件等会影响当前环境的内容，禁止使用廉价LLM!
- 避免使用廉价LLM编写代码或进行复杂决策，因为廉价LLM的代码质量可能较差
- 在调用廉价LLM前，首先在规划中列出当前需要读取的内容，需要探索的目标
- 廉价LLM最多只能用于5个连续消息，超过后会自动切换回普通LLM
  - 如果廉价LLM提前完成了任务则需要调用工具切换回普通LLM（将计数器设置为0）
"""
            content = f"""
# 廉价LLM状态

{status}

{intro}

{rules}
"""
        else:
            status = "廉价LLM模式不可用，请勿使用廉价LLM"
            content = f"""
# 廉价LLM状态

{status}
"""
        return {
            "role": "system",
            "content": content,
        }

    def to_json(self) -> str:
        data = {"is_cheap_llm_available": self.is_cheap_llm_available}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"):
        data = json.loads(json_str)
        return cls(is_cheap_llm_available=data["is_cheap_llm_available"])

class Agent:
    """Agent核心类，负责处理消息流、调用工具和管理状态机。"""

    def __init__(
        self,
        config: AgentConfig,
        group_chat: GroupChat,
        init_messages: Sequence[Message],
    ):
        """
        初始化Agent

        参数:
            config: Agent配置
            group_chat: 与其他类进行通信的类
        """
        self.config = config
        self.group_chat = group_chat

        group_chat.register_queue("agent_user_input")
        group_chat.register_member("agent", self)

        self.state: AgentState = "waiting_user"

        self.messages: list[Message] = list(init_messages)

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

        # 添加LLM切换工具
        llm_toolset = ToolSet()

        # 处理缺少llm_names的情况
        llm_names = self.config.get("llm_names", [f"llm{i}" for i in range(len(self.config["llms"]))])

        @llm_toolset.register_tool(
            name="switch_llm",
            desc="切换到指定的LLM。可用的LLM包括: " + ", ".join(llm_names),
            args={
                "llm_name": ToolArgInfo(
                    desc="要切换到的LLM名称", type="str"
                ),
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
            self.config["current_llm_index"] = index
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
            current_name = llm_names[self.config["current_llm_index"]]
            return f"当前使用的LLM: {current_name}"

        # 将工具集添加到ToolManager
        self.group_chat.get_members("tool_manager", ToolManager).add_toolset(llm_toolset)

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
            chat_msg = await self.group_chat.receive("agent_user_input")
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
        if not self.group_chat.is_empty("agent_user_input"):
            try:
                msg = await self.group_chat.receive("agent_user_input")
                await self.handle_messages([cast(ChatMessage, msg)])
            except QueueEmpty:
                logger.info("用户输入队列已关闭")
            except RuntimeError as e:
                logger.error("处理消息时出错: %s", str(e))
                self.state = "paused"
                raise RuntimeError("处理消息时出错") from e
        else:
            await self.generate_response()

        if self.last_token_usage and self.last_token_usage > self.config.get(
            "compress_threshold_soft", int(65536 * 0.5)
        ):
            hard_threshold = self.config.get(
                "compress_threshold_hard", int(65536 * 0.8)
            )
            percentage = (self.last_token_usage / hard_threshold) * 100
            remaining = hard_threshold - self.last_token_usage
            self.messages.append(
                RuntimeMessage(
                    f"当前Token用量为{self.last_token_usage}，已达到软限制。硬限制为{hard_threshold}，当前使用{percentage:.1f}%，还有{remaining} token直到强制压缩。"
                )
            )

        if self.last_token_usage and self.last_token_usage > self.config.get(
            "compress_threshold_hard", int(65536 * 0.8)
        ):
            # await self.compress()
            await compress_history_range(self)

    async def state_paused(self):
        """
        处理暂停运行状态。

        在这个状态下，Agent会等待用户输入来恢复运行，
        通常用于处理错误或异常情况后的恢复。
        """
        logger.info("Agent进入暂停运行状态")
        try:
            msg = await self.group_chat.receive("agent_user_input")
            self.state = "waiting_user"
            await self.handle_messages([cast(ChatMessage, msg)])
        except QueueEmpty:
            logger.info("用户输入队列已关闭")
        except (RuntimeError, asyncio.CancelledError) as e:
            logger.error("处理消息时出错: %s", str(e))
            raise RuntimeError("处理消息时出错") from e

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

        # 检查是否是workflow工具
        workflow = self.group_chat.get_members(
            "tool_manager", ToolManager
        ).get_workflow(tool_call.function_name)
        if workflow:
            workflow_function = workflow["func"]
            return await workflow_function(self)

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
                # 自动转到自动运行state
                if self.state == "waiting_user":
                    self.state = "working"
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
                tool_result = await self.group_chat.get_members(
                    "tool_manager", ToolManager
                ).process_tool_call(tool_call)
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
        根据当前LLM索引或用户@指定选择合适的模型。

        返回:
            LanguageModel: 选择的语言模型实例
        """
        # 从当前消息往回找，找到最近一个使用了@的消息
        for msg in reversed(self.messages):
            if not isinstance(msg, ChatMessage) or msg.role != "user":
                continue
            content = msg.message.strip()
            if not content.startswith('@'):
                continue
            llm_name = content.split(maxsplit=1)[0][1:]  # 提取@后的名称
            if llm_name not in self.config["llm_names"]:
                continue
            return self.config["llms"][self.config["llm_names"].index(llm_name)]
        
        # 没有找到有效的@消息，使用默认索引
        return self.config["llms"][self.config["current_llm_index"]]

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
            self, enable_compress, disable_waiting_user_warning
        )

        # 选择模型
        model = await self._select_model()

        answer: Answer = await model.answer_stream(self.messages)

        async for token in answer:
            await self.group_chat.send("cli_user_output", token)

            # 实时检查工具调用量（通过lifecycle回调处理）
            current_content = answer.get_current_content()

            # 触发消息生成中的生命周期事件
            should_interrupt = await self.lifecycle.trigger_during_message_generation(
                self, answer, current_content
            )
            if should_interrupt:
                return await self.generate_response()

            if not self.group_chat.is_empty("agent_user_input"):
                await self.group_chat.send("cli_user_output", answer)
                chat_message = cast(ChatMessage, answer.get_message())
                self.messages.append(chat_message)
                self.messages.append(RuntimeMessage("用户打断了你的回答"))
                self.messages.append(await self.group_chat.receive("agent_user_input"))
                answer.interrupt()
                return await self.generate_response()

        await self.group_chat.send("cli_user_output", answer)

        chat_message = cast(ChatMessage, answer.get_message())
        full_response = chat_message.message
        self.messages.append(chat_message)

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

        # 保存对话历史
        await self.save_conversation_history()
        return answer

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
    group_chat: GroupChat,
    config_path: str | Path = "./config.toml",
    llm_name: str | None = None,
):
    config = load_config(config_path)

    # 创建多个LLM实例
    llms = []
    for llm_config in config.llm:
        llm = OpenAi(
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            openai_config=llm_config.model_dump().get("openai_config", {}),
            chat_completion_kwargs=llm_config.model_dump().get(
                "chat_completion_kwargs", {}
            ),
        )
        llms.append(llm)

    # 解析tool_confirmation配置
    tool_confirmation_config = {}
    if config.agent and config.agent.tool_confirmation:
        tool_confirmation_config = config.agent.tool_confirmation

    # 设置压缩阈值
    # 设置默认阈值（比例0.8和0.5对应的token量）
    compress_threshold_hard = int(65536 * 0.8)
    compress_threshold_soft = int(65536 * 0.5)

    if config.agent:
        # 处理compress_threshold_hard
        if isinstance(config.agent.compress_threshold_hard, float):
            compress_threshold_hard = int(65536 * config.agent.compress_threshold_hard)
        elif isinstance(config.agent.compress_threshold_hard, int):
            compress_threshold_hard = config.agent.compress_threshold_hard
        else:
            raise TypeError("compress_threshold_hard must be int or float")

        # 处理compress_threshold_soft
        if isinstance(config.agent.compress_threshold_soft, float):
            compress_threshold_soft = int(65536 * config.agent.compress_threshold_soft)
        elif isinstance(config.agent.compress_threshold_soft, int):
            compress_threshold_soft = config.agent.compress_threshold_soft
        else:
            raise TypeError("compress_threshold_soft must be int or float")

    # 处理llm_name参数
    llm_names = [llm_config.name for llm_config in config.llm]
    current_llm_index = 0  # 默认使用第一个LLM
    if llm_name is not None:
        if llm_name in llm_names:
            current_llm_index = llm_names.index(llm_name)
        else:
            available_llms = ", ".join(llm_names)
            raise ValueError(f"LLM名称 '{llm_name}' 不存在。可用的LLM包括: {available_llms}")

    agent_config: AgentConfig = {
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "llms": llms,
        "llm_names": llm_names,
        "current_llm_index": current_llm_index,
        "compress_threshold_hard": compress_threshold_hard,
        "compress_threshold_soft": compress_threshold_soft,
        "tool_confirmation": tool_confirmation_config,
    }

    tool_manager = ToolManager(group_chat=group_chat, toolsets=[global_tools])
    tool_manager.register_workflow(
        "compress_history_range",
        "压缩指定范围的历史消息：总结并删除指定范围内的消息。调用这个工具来开始压缩指定范围的流程。",
        compress_history_range,
    )

    init_messages: list[Message] = [
        SystemMessage(
            template=agent_config["system_prompt"],
            current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            group_chat=group_chat,
        )
    ]

    # 定义要检查的文件路径列表（按优先级顺序）
    memory_filepaths = [
        Path("~/.config/linhai/LINHAI.md").expanduser(),
        Path("./LINHAI.md").absolute(),
        Path("./AGENT.md").absolute(),
        Path("./CLAUDE.md").absolute(),
    ]

    # 如果配置中指定了文件路径，则使用配置的路径（最高优先级）
    if config.memory is not None and config.memory.file_path:
        memory_filepaths.insert(0, Path(config.memory.file_path).absolute())

    found = False
    for filepath in memory_filepaths:
        if filepath.exists():
            found = True
            init_messages.append(GlobalMemory(filepath))  # 总是添加，无论文件是否存在
    if not found:
        init_messages.append(GlobalMemory(memory_filepaths[0]))

    # 添加廉价LLM状态消息
    init_messages.append(CheapLlmStatusMessage("cheap_model" in agent_config))

    Agent(
        config=agent_config,
        group_chat=group_chat,
        init_messages=init_messages,
    )

    return group_chat
