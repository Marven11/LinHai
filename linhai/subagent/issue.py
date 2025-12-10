"""Issue系统管理模块，负责Agent和SubAgent之间的issue交互。"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import TypedDict


class IssueError(Enum):
    """Issue错误类型枚举。"""

    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    OTHER_ERROR = "OTHER_ERROR"


from linhai.agent.base import RuntimeMessage
from linhai.group_chat import GroupChat
from linhai.utils import CliRuntimeNotice


# 定义需要等待时间的subagent类型
WAITING_SUBAGENT_TYPES = {"git_diff_reviewer"}


# 不再使用IssueLimitExceededError异常，改为直接返回错误字符串


class Issue(TypedDict):
    """Issue数据结构"""

    id: str
    content: str
    from_subagent: str  # subagent名称
    created_at: datetime
    answered: bool
    answer: str | None
    min_response_interval: timedelta  # 新增：最低回复间隔


class IssueManager:
    """Issue管理器，负责管理Agent和SubAgent之间的issue。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
        self.subagent_issue_count: dict[str, int] = {}  # subagent名称 -> issue计数
        self.subagent_limits: dict[str, int] = {}  # subagent名称 -> issue限额
        self.issues: dict[str, Issue] = {}
        self._response_events: dict[str, asyncio.Event] = {}
        group_chat.register_member("issue_manager", self)

    def register_subagent(self, subagent_name: str, issue_limit: int = 1):
        """注册subagent的issue限额。"""
        self.subagent_limits[subagent_name] = issue_limit

    def get_subagent_type(self, subagent_name: str) -> str | None:
        """获取subagent的类型。

        Returns:
            str: subagent的类型字符串
            None: 如果subagent不存在
        """
        from linhai.subagent.main import SubAgentManager

        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )
        assert subagent_manager is not None

        if subagent_name not in subagent_manager.subagents:
            return None

        subagent, _ = subagent_manager.subagents[subagent_name]
        return subagent.agent_type

    def get_subagent_issue_limit(self, subagent_name: str) -> int:
        """获取subagent的issue限额，默认返回1。"""
        return self.subagent_limits.get(subagent_name, 1)

    def has_unanswered_issues(self) -> bool:
        """检查是否有未解答的issue。"""
        return any(not i["answered"] for i in self.issues.values())

    async def add_issue(self, issue_id: str, content: str, from_subagent: str) -> None:
        """添加一个新的issue。"""
        # 根据subagent类型确定最低回复间隔
        min_response_interval: timedelta
        subagent_type = self.get_subagent_type(from_subagent)
        if subagent_type in WAITING_SUBAGENT_TYPES:
            min_response_interval = timedelta(minutes=2)
        else:
            min_response_interval = timedelta(seconds=0)  # 可以立即回答

        self.issues[issue_id] = {
            "id": issue_id,
            "content": content,
            "from_subagent": from_subagent,
            "created_at": datetime.now(),
            "answered": False,
            "answer": None,
            "min_response_interval": min_response_interval,
        }
        self._response_events[issue_id] = asyncio.Event()

        # 通知Agent，但不强制立即回答
        from linhai.agent.message import AgentMessage

        agent_message = self.group_chat.get_members("agent_message", AgentMessage)
        agent_message.append_message(
            RuntimeMessage(
                f"收到来自SubAgent(@{from_subagent})的issue，ID为{issue_id}。\n"
                f"内容: {content}\n"
                "你可以使用list_issues工具查看issue及其可回答时间。\n"
                "请先完成相关任务，再回答issue。"
            )
        )

        from linhai.agent.main import Agent

        agent = self.group_chat.get_members("agent", Agent)
        if agent.state == "waiting_user":
            agent.state = "working"

    async def request_issue(self, issue_id: str, content: str, from_subagent: str):
        """请求issue并通知Agent，返回错误信息"""
        if from_subagent not in self.subagent_issue_count:
            self.subagent_issue_count[from_subagent] = 0

        limit = self.get_subagent_issue_limit(from_subagent)
        if self.subagent_issue_count[from_subagent] >= limit:
            raise RuntimeError("达到issue限额后subagent还未退出")
        self.subagent_issue_count[from_subagent] += 1
        await self.add_issue(issue_id, content, from_subagent)

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="INFO", content=f"SubAgent添加了issue请求{issue_id}"
            ),
        )
        return

    async def wait_for_response(self, issue_id: str) -> str:
        """等待指定issue的回复。"""
        if issue_id not in self._response_events:
            raise ValueError(f"Issue {issue_id} 不存在")

        await self._response_events[issue_id].wait()
        issue = self.issues[issue_id]
        assert issue["answer"] is not None
        return issue["answer"]

    def respond_issue(self, issue_id: str, answer: str) -> str:
        """回复一个issue。返回成功或错误消息。"""
        if issue_id not in self.issues:
            return f"错误: Issue {issue_id} 不存在"

        issue = self.issues[issue_id]

        time_since_creation = datetime.now() - issue["created_at"]
        if time_since_creation < issue["min_response_interval"]:
            # 提前回答，完全阻止回答，只返回提示，不修改issue状态
            return "警告: issue的最低回复间隔未到。请先完成其他任务，稍后再回答！"

        issue["answered"] = True
        issue["answer"] = answer

        if issue_id in self._response_events:
            self._response_events[issue_id].set()

        return f"成功回复issue {issue_id}"

    def get_unanswered_issues(self) -> list[Issue]:
        """获取所有未解答的issue列表。"""
        return [i for i in self.issues.values() if not i["answered"]]

    def get_issue_info(self, issue_id: str) -> str | None:
        """获取issue的详细信息，包括可回答时间。"""
        if issue_id not in self.issues:
            return None
        issue = self.issues[issue_id]
        time_since_creation = datetime.now() - issue["created_at"]
        time_remaining = issue["min_response_interval"] - time_since_creation
        if time_remaining.total_seconds() > 0:
            return (
                f"Issue {issue_id} 可回答时间: {time_remaining.total_seconds():.0f}秒后"
            )
        else:
            return f"Issue {issue_id} 可以立即回答"

    def is_issue_limit_exceeded(self, subagent_name: str) -> bool:
        assert (
            subagent_name in self.subagent_issue_count
            and subagent_name in self.subagent_limits
        ), "subagent不存在"
        return (
            self.subagent_issue_count[subagent_name]
            >= self.subagent_limits[subagent_name]
        )
