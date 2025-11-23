"""SubAgent核心实现。"""

import asyncio
import logging
import json
from reprlib import Repr
from typing import TypedDict
from datetime import datetime

from linhai.llm import (
    Message,
    ChatMessage,
    SubagentSystemMessage,
    LanguageModel,
    Answer,
    AnswerToken,
)
from linhai.group_chat import GroupChat
from linhai.tool.base import ToolSet, ToolArgInfo, to_tools_info
from linhai.tool.tools.command import sleep_tool
from linhai.agent.base import RuntimeMessage
from linhai.markdown_parser import extract_tool_calls_with_errors
from linhai.utils import CliRuntimeNotice
from linhai.prompt import SUBAGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
reprobj = Repr(maxstring=50)


class SubAgentContext(TypedDict):
    """SubAgent配置参数"""

    type: str
    name: str
    task_message: str
    llm: LanguageModel


class SubAgent:
    """SubAgent类，简化版Agent，无用户交互，执行单一任务后退出。"""

    def __init__(self, context: SubAgentContext, group_chat: GroupChat):
        self.context = context
        self.group_chat = group_chat
        self.state: str = "running"
        self.exit_reason: str | None = None
        self.start_time = datetime.now()

        # SubAgent专用工具集
        self.toolset = ToolSet()
        self._register_subagent_tools()

        # 初始化消息
        self.messages: list[Message] = [
            SubagentSystemMessage(
                SUBAGENT_SYSTEM_PROMPT.replace(
                    "{|TOOLS|}",
                    json.dumps(
                        to_tools_info(self.toolset.get_tools()),
                        ensure_ascii=False,
                    ),
                ),
            ),
            ChatMessage(role="user", message=context["task_message"]),
        ]

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
        def subagent_exit(reason: str) -> str:
            self.exit_reason = reason
            self.state = "exited"
            return f"SubAgent {self.context['name']} 已退出: {reason}"

    async def _generate_response(self) -> str:
        """生成LLM响应并返回完整内容，支持流式输出。"""
        answer: Answer = await self.context["llm"].answer_stream(self.messages)

        full_response = ""
        async for token in answer:
            if isinstance(token, AnswerToken):
                full_response += token.content
                # 发送流式token到队列
                await self.group_chat.send_if_exists(
                    "subagent_message",
                    {
                        "subagent_name": self.context['name'],
                        "content": token.content,
                        "type": "token",
                        "is_reasoning": token.reasoning_content is not None,
                    },
                )
            elif isinstance(token, str):
                full_response += token
                # 对于字符串token，也发送
                await self.group_chat.send_if_exists(
                    "subagent_message",
                    {
                        "subagent_name": self.context['name'],
                        "content": token,
                        "type": "token",
                        "is_reasoning": False,
                    },
                )

        # 发送完成消息
        await self.group_chat.send_if_exists(
            "subagent_message",
            {
                "subagent_name": self.context['name'],
                "content": full_response,
                "type": "message_complete"
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
                        self.messages.append(
                            ChatMessage(
                                role="user", message=f"工具 {tool_name} 执行失败: {e}"
                            )
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

        # 如果没有工具调用，添加提示继续
        if not tool_calls:
            self.messages.append(
                ChatMessage(role="user", message="请使用工具完成任务并调用exit退出")
            )

        return self.state == "running"

    async def run(self) -> None:
        """运行SubAgent，执行任务直到退出。"""
        logger.info("SubAgent %s 启动", self.context["name"])

        while self.state == "running":
            should_continue = await self._handle_execution_cycle()
            if not should_continue:
                break

        logger.info(
            "SubAgent %s 结束运行，原因: %s", self.context["name"], self.exit_reason
        )
        
        # 发送退出通知到subagent标签页
        await self.group_chat.send_if_exists(
            "subagent_message",
            {
                "subagent_name": self.context['name'],
                "content": f"SubAgent {self.context['name']} 已退出: {self.exit_reason}",
                "type": "runtime_notice",
                "level": "INFO"
            },
        )


class SubAgentManager:
    """SubAgent管理器，负责创建和管理所有SubAgent。"""

    def __init__(self, group_chat: GroupChat, subagent_config = None, llms = None, llm_names = None):
        self.group_chat = group_chat
        self.subagent_config = subagent_config
        self.llms = llms or []
        self.llm_names = llm_names or []
        self.subagents: dict[str, tuple[SubAgent, asyncio.Task | None]] = {}
        group_chat.register_member("subagent_manager", self)

    async def create_subagent(
        self, agent_type: str, name: str, task_message: str, llm: LanguageModel
    ) -> str:
        """创建并启动一个SubAgent。"""
        if name in self.subagents:
            return f"错误: SubAgent {name} 已存在"

        # 使用subagent配置中的default_llm，如果没有配置则使用传入的llm
        from linhai.llm import LanguageModel
        subagent_llm: LanguageModel = llm
        
        if self.subagent_config and hasattr(self.subagent_config, 'default_llm'):
            default_llm_name = self.subagent_config.default_llm
            if default_llm_name in self.llm_names:
                llm_index = self.llm_names.index(default_llm_name)
                subagent_llm = self.llms[llm_index]

        context: SubAgentContext = {
            "type": agent_type,
            "name": name,
            "task_message": task_message,
            "llm": subagent_llm,
        }

        subagent = SubAgent(context, self.group_chat)

        # 安全地创建任务（检查是否有运行的事件循环）
        try:
            loop = asyncio.get_running_loop()
            task = asyncio.create_task(subagent.run())
        except RuntimeError:
            # 没有运行的事件循环，稍后启动
            task = None

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
