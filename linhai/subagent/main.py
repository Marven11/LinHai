"""SubAgent核心实现。"""

import asyncio
import logging
from datetime import datetime
from typing import Sequence

from linhai.agent.base import RuntimeMessage
from linhai.config import SubAgentConfig
from linhai.group_chat import GroupChat
from linhai.llm import (
    Answer,
    AnswerToken,
    ChatMessage,
    LanguageModel,
    Message,
    SubagentSystemMessage,
)
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.tool.base import ToolSet, ToolArgInfo
from linhai.tool.tools.command import sleep_tool

logger = logging.getLogger(__name__)


class SubAgent:
    """SubAgent类，简化版Agent，无用户交互，执行单一任务后退出。"""

    def __init__(
        self,
        agent_type: str,
        name: str,
        task_message: str,
        llm: LanguageModel,
        group_chat: GroupChat,
        max_answer_times: int | None,
        initial_messages: Sequence[Message] | None = None,
    ):
        self.agent_type = agent_type
        self.name = name
        self.task_message = task_message
        self.llm = llm
        self.group_chat = group_chat
        self.state: str = "running"
        self.exit_reason: str | None = None
        self.start_time = datetime.now()
        self.max_answer_times = max_answer_times

        self.toolset = ToolSet()
        self._register_subagent_tools()

        self.messages: list[Message] = [
            SubagentSystemMessage(self.get_system_message_prompt()),
        ]

        if initial_messages:
            self.messages.extend(initial_messages)

        self.messages.append(ChatMessage(role="user", message=self.task_message))

    def get_system_message_prompt(self):
        raise NotImplementedError()

    def _register_subagent_tools(self):
        """注册SubAgent可用的工具。"""

        @self.toolset.register_tool(
            name="sleep",
            desc="睡眠X秒，返回开始和结束时间",
            args={"seconds": ToolArgInfo(desc="睡眠的秒数", type="float")},
            required_args=["seconds"],
        )
        async def subagent_sleep(seconds: float) -> str:
            return await sleep_tool(seconds)

        @self.toolset.register_tool(
            name="exit",
            desc="退出SubAgent并提供退出原因",
            args={"reason": ToolArgInfo(desc="退出原因", type="str")},
            required_args=["reason"],
        )
        async def subagent_exit(reason: str) -> str:
            self.exit_reason = reason
            self.state = "exited"
            return f"SubAgent {self.name} 已退出: {reason}"

        from linhai.subagent.clarification import ClarificationManager
        from .clarification_tools import create_clarification_toolset

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )

        if isinstance(clarification_manager, tuple):
            clarification_manager = clarification_manager[0]
        clarification_toolset = create_clarification_toolset(
            clarification_manager, self.name
        )
        self.toolset.add_toolset(clarification_toolset)

        # 注册SubAgent专用的todolist_delete工具
        from linhai.tool.tools.todolist import TodolistManager

        todolist_manager = self.group_chat.get_members(
            "todolist_manager", TodolistManager
        )

        @self.toolset.register_tool(
            name="todolist_delete",
            desc="根据ID删除todolist（仅SubAgent可用）",
            args={
                "todolist_id": ToolArgInfo(desc="要删除的todolist ID", type="str"),
            },
            required_args=["todolist_id"],
        )
        async def subagent_todolist_delete(todolist_id: str) -> str:
            """根据ID删除todolist（仅SubAgent可用）。"""
            # 先检查todolist是否存在
            todolist = todolist_manager.get_todolist_by_id(todolist_id)
            if todolist is None:
                raise ValueError(f"Todolist with ID {todolist_id} does not exist")

            todolist_manager.delete_todolist(todolist_id)
            return f"成功删除todolist: {todolist_id} ({todolist['content']})"

    async def _generate_response(self) -> str:
        """生成LLM响应并返回完整内容，支持流式输出。"""
        answer: Answer = await self.llm.answer_stream(self.messages)

        full_response = ""
        async for token in answer:
            if isinstance(token, AnswerToken):
                full_response += token.content

                await self.group_chat.send_if_exists(
                    "subagent_message",
                    {
                        "subagent_name": self.name,
                        "content": token.content,
                        "type": "token",
                        "is_reasoning": token.reasoning_content is not None,
                    },
                )

        await self.group_chat.send_if_exists(
            "subagent_message",
            {
                "subagent_name": self.name,
                "content": full_response,
                "type": "message_complete",
            },
        )

        return full_response

    def _parse_tool_calls(self, full_response: str) -> tuple[list[dict], list[str]]:
        """解析工具调用和错误。"""
        return extract_tool_calls_with_errors(full_response)

    async def _execute_tool_calls(self, tool_calls: list[dict]) -> None:
        """执行工具调用并处理结果。"""
        for call in tool_calls:
            if "name" in call and "arguments" in call:
                tool_name = call["name"]
                tool_args = call["arguments"]

                if self.toolset.has_tool(tool_name):
                    try:
                        result = await self.toolset.call_tool(tool_name, tool_args)
                        self.messages.append(
                            ChatMessage(
                                role="user", message=f"工具 {tool_name} 返回: {result}"
                            )
                        )
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        error_msg = f"工具 {tool_name} 执行失败: {e}"
                        self.messages.append(
                            ChatMessage(role="user", message=error_msg)
                        )
                        from linhai.utils import CliRuntimeNotice

                        await self.group_chat.send_if_exists(
                            "subagent_message",
                            CliRuntimeNotice(
                                level="ERROR",
                                content=f"SubAgent {self.name} 工具 {tool_name} 执行失败: {error_msg}",
                            ),
                        )
                else:
                    self.messages.append(
                        ChatMessage(role="user", message=f"未知工具: {tool_name}")
                    )

    async def _handle_execution_cycle(self) -> bool:
        """执行一个完整的处理周期，返回是否应继续运行。"""
        full_response = await self._generate_response()
        tool_calls, errors = self._parse_tool_calls(full_response)

        for error in errors:
            self.messages.append(RuntimeMessage(error))

        await self._execute_tool_calls(tool_calls)

        if not tool_calls:
            self.messages.append(ChatMessage(role="user", message="请调用工具！"))

        return self.state == "running"

    async def run(self) -> None:
        """运行SubAgent，执行任务直到退出。"""

        if hasattr(self.group_chat, "_test_mode"):
            logger.info("SubAgent %s 在测试模式中跳过运行", self.name)
            return

        logger.info("SubAgent %s 启动", self.name)

        while self.state == "running":
            should_continue = await self._handle_execution_cycle()
            if not should_continue:
                break
            if self.max_answer_times:
                self.max_answer_times -= 1
                if self.max_answer_times <= 0:
                    break

        logger.info("SubAgent %s 结束运行，原因: %s", self.name, self.exit_reason)

        # 发送SubAgent退出通知到UI
        from linhai.utils import CliRuntimeNotice

        await self.group_chat.send_if_exists(
            "subagent_message",
            CliRuntimeNotice(
                level="INFO", content=f"SubAgent {self.name} 已退出: {self.exit_reason}"
            ),
        )


class SubAgentManager:
    """SubAgent管理器，负责创建和管理所有SubAgent。"""

    def __init__(
        self,
        group_chat: GroupChat,
        subagent_config: SubAgentConfig | None,
        llms=None,
        llm_names=None,
    ):
        assert subagent_config is not None, "subagent_config不能为None"
        self.group_chat = group_chat
        self.subagent_config = subagent_config
        self.llms = llms or []
        self.llm_names = llm_names or []
        self.subagents: dict[str, tuple[SubAgent, asyncio.Task | None]] = {}
        group_chat.register_member("subagent_manager", self)

    async def create_subagent(
        self,
        agent_type: str,
        name: str,
        task_message: str,
        max_answer_times: int | None,
        initial_messages: Sequence[Message] | None = None,
    ) -> str:
        """创建并启动一个SubAgent。"""
        if name in self.subagents:
            return f"错误: SubAgent {name} 已存在"

        subagent_llm: LanguageModel | None = None

        if self.subagent_config and self.subagent_config.default_llm:
            default_llm_name = self.subagent_config.default_llm
            if default_llm_name in self.llm_names:
                llm_index = self.llm_names.index(default_llm_name)
                subagent_llm = self.llms[llm_index]

        if subagent_llm is None:
            from linhai.agent.main import Agent

            agent = self.group_chat.get_members("agent", Agent)
            _, subagent_llm = agent.get_current_llm_info()

        from .types import (
            ViolationCheckerSubAgent,
            GitDiffReviewerSubAgent,
        )

        SUBAGENT_CREATORS = {
            "violation_checker": ViolationCheckerSubAgent,
            "git_diff_reviewer": GitDiffReviewerSubAgent,
        }

        if agent_type not in SUBAGENT_CREATORS:
            raise ValueError(f"未知的SubAgent类型: {agent_type}")

        subagent_class = SUBAGENT_CREATORS[agent_type]
        subagent = subagent_class(
            name=name,
            task_message=task_message,
            llm=subagent_llm,
            group_chat=self.group_chat,
            max_answer_times=max_answer_times,
            initial_messages=initial_messages,
        )

        task = asyncio.create_task(subagent.run())

        self.subagents[name] = (subagent, task)

        return f"成功创建SubAgent {name} (类型: {agent_type})"

    async def check_subagent(self, name: str) -> str:
        """检查SubAgent状态。"""
        if name not in self.subagents:
            return f"错误: SubAgent {name} 不存在"

        subagent, task = self.subagents[name]
        status = subagent.state
        duration = (datetime.now() - subagent.start_time).total_seconds()

        if task and task.done():
            await task
            self.subagents[name] = (subagent, None)

        if status == "exited":
            return f"SubAgent {name} 已退出，运行时长: {duration:.1f}秒，退出原因: {subagent.exit_reason}"
        else:
            return f"SubAgent {name} 正在运行，已运行: {duration:.1f}秒"

    async def cleanup_exited_subagents(self) -> None:
        """清理已退出的SubAgent。"""

        for _, task in self.subagents.values():
            if task and task.done():
                await task

    def register_plugins(self) -> None:
        """注册SubAgent相关的插件。"""
        from linhai.agent import Lifecycle

        lifecycle = self.group_chat.get_members("lifecycle", Lifecycle)

        from .plugin import (
            GitBlockingPlugin,
            ClarificationWaitingUserPlugin,
            ClarificationBlockingPlugin,
        )
        from .types.violation_checker import ViolationCheckerPlugin
        from .types.git_diff_reviewer import GitDiffReviewPlugin

        plugins = [
            GitBlockingPlugin(self.group_chat),
            ClarificationWaitingUserPlugin(self.group_chat),
            ClarificationBlockingPlugin(self.group_chat),
        ]
        enabled_agent_types = (
            self.subagent_config.enabled_agent_types if self.subagent_config else None
        )

        if enabled_agent_types and enabled_agent_types.violation_checker:
            plugins.append(ViolationCheckerPlugin(self.group_chat))
        if enabled_agent_types and enabled_agent_types.git_diff_reviewer:
            plugins.append(GitDiffReviewPlugin(self.group_chat))

        for plugin in plugins:
            plugin.register(lifecycle)
