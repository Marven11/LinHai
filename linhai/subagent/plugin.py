"""SubAgent通用插件实现。"""

import shlex
import os

from linhai.llm import ToolCallMessage, Answer
from linhai.utils import CliRuntimeNotice
from linhai.agent.plugin import Plugin
from linhai.agent.base import RuntimeMessage, WAITING_USER_MARKER


class GitBlockingPlugin(Plugin):
    """阻止Agent在有未解答issue时使用git命令的Plugin。"""

    async def before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        """检查是否有未解答的issue，如果有则阻止使用git命令。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.subagent.issue import IssueManager

        issue_manager = self.group_chat.get_members("issue_manager", IssueManager)
        if issue_manager and issue_manager.has_unanswered_issues():

            tool_name = tool_call.function_name
            arguments = tool_call.function_arguments

            if tool_name in ["run_command"]:
                command = arguments.get("command", "")

                if self._is_git_command(command):
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
                            f"命令 '{command}' 被识别为git命令，请先回复所有SubAgent的issue。\n"
                            f"未解答的issue:\n{issue_info}"
                        )
                    )

                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="ERROR", content=f"Git命令被阻止: {command}"
                        ),
                    )

                    return True
        return False

    def _is_git_command(self, command: str) -> bool:
        """精确检测是否为git命令"""

        try:
            parts = shlex.split(command.strip())
            if not parts:
                return False

            cmd = parts[0]

            if cmd == "git":
                return True

            if cmd.startswith("git-"):
                return True

            basename = os.path.basename(cmd)
            if basename == "git" or basename == "git.exe":
                return True

            return False
        except (ValueError, OSError):
            return False

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到before_tool_call回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)


class IssueWaitingUserPlugin(Plugin):
    """阻止Agent在有未解答issue时进入等待用户状态的Plugin。"""

    async def before_waiting_user(self, agent: "linhai.agent.Agent"):
        """检查是否有未解答的issue，如果有则阻止进入等待用户状态。"""

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

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
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

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
