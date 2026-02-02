"""SubAgent通用插件实现。"""

import shlex
import os

from linhai.llm import ToolCallMessage, Answer, Message
from linhai.utils import CliRuntimeNotice
from linhai.plugin import Plugin
from linhai.agent.base import RuntimeMessage, WAITING_USER_MARKER

from typing import TYPE_CHECKING, Literal, Union

if TYPE_CHECKING:
    from linhai.agent import Agent, Lifecycle


class GitBlockingPlugin(Plugin):
    """阻止Agent在有未解答issue时使用git命令的Plugin。"""

    async def on_tool_result(
        self,
        tool_name: str,
        tool_index: int,
        status: Literal["skipped", "success", "failed"],
        message: Message | None,
        toolcall_arguments: dict | None,
        with_secret: list[str] | None,
        is_tool_failed_duplicated_error: bool,
    ) -> Union[None, bool, RuntimeMessage]:
        """检查是否有未解答的issue，如果有则阻止使用git命令。"""
        if status != "skipped":
            return None

        from linhai.agent import Agent
        from linhai.subagent.issue import IssueManager

        issue_manager = self.group_chat.get_members("issue_manager", IssueManager)
        if not issue_manager or not issue_manager.has_unanswered_issues():
            return None

        if tool_name != "process_create":
            return None

        if toolcall_arguments is None:
            return None

        command_list = toolcall_arguments.get("command")
        if not command_list:
            return None
        cmd = command_list[0]
        if not (
            cmd == "git"
            or cmd.startswith("git-")
            or os.path.basename(cmd) in ("git", "git.exe")
        ):
            return None

        agent = self.group_chat.get_members("agent", Agent)
        unanswered = issue_manager.get_unanswered_issues()
        issue_info = "\n".join(
            [
                f"  ID: {i['id']}, 来自: {i['from_subagent']}, 内容: {i['content']}"
                for i in unanswered
            ]
        )
        agent.message_processor.add_new_message(
            RuntimeMessage(
                f"错误：有未解答的issue，禁止使用git命令。"
                f"命令 '{' '.join(command_list)}' 被识别为git命令，请先回复所有SubAgent的issue。\n"
                f"未解答的issue:\n{issue_info}"
            )
        )

        await self.group_chat.send_if_exists(
            "ui_log",
            CliRuntimeNotice(
                level="ERROR",
                content=f"Git命令被阻止: {' '.join(command_list)}",
            ),
        )

        return True

    def register(self, lifecycle: "Lifecycle"):
        """注册到on_tool_result回调。"""
        lifecycle.register_on_tool_result(self.on_tool_result)


class IssueWaitingUserPlugin(Plugin):
    """阻止Agent在有未解答issue时进入等待用户状态的Plugin。"""

    async def before_waiting_user(self, agent: "Agent"):
        """检查是否有未解答的issue，如果有则阻止进入等待用户状态。"""
        from linhai.agent import Agent
        from linhai.subagent.issue import IssueManager

        issue_manager = self.group_chat.get_members("issue_manager", IssueManager)
        if issue_manager and issue_manager.has_unanswered_issues():
            unanswered = issue_manager.get_unanswered_issues()
            issue_info = "\n".join(
                [
                    f"  ID: {i['id']}, 来自: {i['from_subagent']}, 内容: {i['content']}"
                    for i in unanswered
                ]
            )
            agent.message_processor.add_new_message(
                RuntimeMessage(
                    f"错误：有未解答的issue，禁止进入等待用户状态。\n"
                    f"未解答的issue:\n{issue_info}"
                )
            )
            agent.state = "working"

    def register(self, lifecycle: "Lifecycle"):
        """注册到before_waiting_user回调。"""
        lifecycle.register_before_waiting_user(self.before_waiting_user)


class IssueBlockingPlugin(Plugin):
    """阻止Agent在有未解答issue时停下等待用户的Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response: str, _tool_calls
    ):
        """检查是否有未解答的issue，如果有则阻止使用等待用户标记。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.subagent.issue import IssueManager

        issue_manager = self.group_chat.get_members("issue_manager", IssueManager)
        if issue_manager.has_unanswered_issues():

            if WAITING_USER_MARKER in full_response:
                unanswered = issue_manager.get_unanswered_issues()
                issue_info = "\n".join(
                    [
                        f"  ID: {i['id']}, 来自: {i['from_subagent']}, 内容: {i['content']}"
                        for i in unanswered
                    ]
                )
                agent.message_processor.add_new_message(
                    RuntimeMessage(
                        f"错误：有未解答的issue，禁止使用{WAITING_USER_MARKER!r}等待用户。\n"
                        f"未解答的issue:\n{issue_info}"
                    )
                )
                agent.state = "working"

    def register(self, lifecycle: "Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
