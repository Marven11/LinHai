"""SubAgent相关插件实现。"""

from typing import Any, TYPE_CHECKING
import asyncio
import logging
import shlex
import os
import subprocess

from linhai.llm import ToolCallMessage, Answer, ChatMessage
from linhai.utils import CliRuntimeNotice, generate_id
from linhai.agent.plugin import Plugin
from linhai.agent.base import RuntimeMessage, WAITING_USER_MARKER
from linhai.prompt import get_subagent_prompt

if TYPE_CHECKING:
    import linhai.agent
    import linhai.subagent

logger = logging.getLogger(__name__)


class SubAgentCollaborationPlugin(Plugin):
    """基于lifecycle事件驱动subagent协作的Plugin。

    在工具失败、工具冲突时启动subagent，检查agent是否违反了多个工具的调用规则。
    """

    async def tool_failure(
        self,
        agent: "linhai.agent.Agent",
        tool_call: ToolCallMessage,
        error: Any,
    ) -> None:
        """在工具调用失败时启动subagent检查规则违反。"""
        assert agent.current_answer is not None

        full_response = agent.current_answer.get_current_content()
        if full_response.count("```json toolcall") <= 1:
            return

        interrupt_msg = CliRuntimeNotice(
            level="WARNING", content="启动SubAgent检查工具调用"
        )
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

        from linhai.subagent import SubAgentManager

        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )

        asyncio.create_task(
            self._check_violations(subagent_manager, full_response, tool_call, error)
        )

    async def tool_conflict(
        self,
        agent: "linhai.agent.Agent",
        tool_call: ToolCallMessage,
        conflicting_tools: list[str],
    ) -> None:
        """在工具调用冲突时启动subagent检查规则违反。"""
        interrupt_msg = CliRuntimeNotice(
            level="WARNING", content="启动SubAgent检查工具冲突"
        )
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

        from linhai.subagent import SubAgentManager

        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )
        assert agent.current_answer is not None

        full_response = agent.current_answer.get_current_content()

        asyncio.create_task(
            self._check_conflict_violations(
                subagent_manager, full_response, tool_call, conflicting_tools
            )
        )

    async def _check_violations(
        self,
        subagent_manager: "linhai.subagent.SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        error: Any,
    ) -> None:
        """在后台任务中检查agent是否违反规则。"""
        check_context = f"""**失败的工具调用详情:**
- 工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 错误信息: {error}"""

        task_message = get_subagent_prompt("violation_checker").format(
            agent_full_response=full_response, check_context=check_context
        )

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    async def _check_conflict_violations(
        self,
        subagent_manager: "linhai.subagent.SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        conflicting_tools: list[str],
    ) -> None:
        """在后台任务中检查agent是否违反规则（工具冲突情况）。"""
        check_context = f"""**工具冲突详情:**
- 冲突工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 与以下工具冲突: {', '.join(conflicting_tools)}"""

        task_message = get_subagent_prompt("violation_checker").format(
            agent_full_response=full_response, check_context=check_context
        )

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到lifecycle回调。"""
        lifecycle.register_tool_failure(self.tool_failure)
        lifecycle.register_tool_conflict(self.tool_conflict)


class GitBlockingPlugin(Plugin):
    """阻止Agent在有未解答澄清时使用git命令的Plugin。"""

    async def before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        """检查是否有未解答的澄清，如果有则阻止使用git命令。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.subagent.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):

            tool_name = tool_call.function_name
            arguments = tool_call.function_arguments

            if tool_name in ["run_command"]:
                command = arguments.get("command", "")

                if self._is_git_command(command):
                    agent.message_processor.append_message(
                        RuntimeMessage(
                            f"错误：有未解答的澄清问题，禁止使用git命令。"
                            f"命令 '{command}' 被识别为git命令，请先回复所有SubAgent的澄清问题。"
                        )
                    )
                    
                    await self.group_chat.send_if_exists(
                        "ui_log",
                        CliRuntimeNotice(
                            level="ERROR", 
                            content=f"Git命令被阻止: {command}"
                        )
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


class ClarificationWaitingUserPlugin(Plugin):
    """阻止Agent在有未解答澄清时进入等待用户状态的Plugin。"""

    async def before_waiting_user(self, agent: "linhai.agent.Agent"):
        """检查是否有未解答的澄清，如果有则阻止进入等待用户状态。"""

        from linhai.subagent.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):
            agent.message_processor.append_message(
                RuntimeMessage(
                    "错误：有未解答的澄清问题，禁止进入等待用户状态。"
                    "请先回复所有SubAgent的澄清问题。"
                )
            )
            agent.state = "working"

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到before_waiting_user回调。"""
        lifecycle.register_before_waiting_user(self.before_waiting_user)


class ClarificationBlockingPlugin(Plugin):
    """阻止Agent在有未解答澄清时停下等待用户的Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response: str, _tool_calls
    ):
        """检查是否有未解答的澄清，如果有则阻止使用等待用户标记。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.subagent.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):

            if WAITING_USER_MARKER in full_response:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"错误：有未解答的澄清问题，禁止使用{WAITING_USER_MARKER!r}等待用户。"
                        "请先使用工具回复所有SubAgent的澄清问题。"
                    )
                )
                agent.state = "working"

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class GitDiffReviewPlugin(Plugin):
    """在Agent使用#LINHAI_WAITING_USER且当前目录是git仓库时启动git diff审查的Plugin。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self._last_git_diff = None
        self._last_new_files_content = None
        self._last_deleted_files_list = None

    def _get_git_diff(self) -> str | None:
        """获取git diff内容，如果失败返回None。"""
        if not os.path.exists(".git"):
            return None

        try:
            result = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_diff = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        if git_diff.strip():
            return git_diff

        try:
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                check=True,
            )
            git_diff = result.stdout
        except subprocess.CalledProcessError:
            return None

        if git_diff.strip():
            return git_diff

        return None

    def _get_new_files_content(self) -> str:
        """获取新增文件的内容，使用--porcelain获取列表并解析。"""
        if not os.path.exists(".git"):
            return ""

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            status_lines = result.stdout.strip().split("\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

        new_files_content = []
        for line in status_lines:
            if not line:
                continue
            status = line[:2]
            filename = line[3:].strip().strip('"')

            if status == "??":
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        content = f.read()
                        new_files_content.append(
                            f"**新增文件: {filename}**\n```\n{content}\n```"
                        )
                except (OSError, UnicodeDecodeError):
                    new_files_content.append(
                        f"**新增文件: {filename}**\n(无法读取文件内容)"
                    )

        return "\n\n".join(new_files_content) if new_files_content else ""

    def _get_deleted_files_list(self) -> str:
        """获取删除文件的列表，包括暂存区和工作区删除。"""
        if not os.path.exists(".git"):
            return ""

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            status_lines = result.stdout.strip().split("\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ""

        deleted_files = []
        for line in status_lines:
            if not line:
                continue
            status = line[:2]
            filename = line[3:].strip().strip('"')

            # 精确检查删除状态：包括工作区删除(' D')、暂存区删除('D ')、重命名删除('RD')等
            # 参考git status文档：https://git-scm.com/docs/git-status
            if status in [" D", "D ", "RD", "AD"]:
                deleted_files.append(filename)

        if deleted_files:
            return "**删除文件列表:**\n" + "\n".join(f"- {filename}" for filename in deleted_files)
        return ""

    async def before_waiting_user(self, agent: "linhai.agent.Agent"):
        """在Agent进入等待用户状态前检查是否需要启动git diff审查。"""
        git_diff = self._get_git_diff()
        if git_diff is None:
            return

        new_files_content = self._get_new_files_content()
        deleted_files_list = self._get_deleted_files_list()

        # 检查是否与上一次完全相同
        if (self._last_git_diff == git_diff and 
            self._last_new_files_content == new_files_content and
            self._last_deleted_files_list == deleted_files_list):
            # 没有变化，发送UI消息通知用户
            no_change_msg = CliRuntimeNotice(
                level="INFO", 
                content="未触发SubAgent审核：检测到与上一次完全相同的git更改，无需重复审查"
            )
            await self.group_chat.send_if_exists("ui_log", no_change_msg)
            return  # 完全没有变化，不启动SubAgent

        # 更新缓存
        self._last_git_diff = git_diff
        self._last_new_files_content = new_files_content
        self._last_deleted_files_list = deleted_files_list

        interrupt_msg = CliRuntimeNotice(
            level="INFO", content="检测到未提交的更改，启动Git diff审查SubAgent"
        )
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

        from linhai.subagent import SubAgentManager

        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )

        messages = agent.message_processor.get_messages()
        user_messages = [
            msg
            for msg in messages
            if isinstance(msg, ChatMessage) and msg.role == "user"
        ]

        full_diff_content = git_diff
        if new_files_content:
            full_diff_content += f"\n\n# 新增文件\n\n{new_files_content}"
        if deleted_files_list:
            full_diff_content += f"\n\n# 删除文件\n\n{deleted_files_list}"

        task_message = get_subagent_prompt("git_diff_reviewer").format(
            git_diff=full_diff_content
        )

        asyncio.create_task(
            subagent_manager.create_subagent(
                agent_type="git_diff_reviewer",
                name=generate_id("git_diff_reviewer"),
                task_message=task_message,
                max_answer_times=5,
                initial_messages=user_messages,
            )
        )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到before_waiting_user回调。"""
        lifecycle.register_before_waiting_user(self.before_waiting_user)
