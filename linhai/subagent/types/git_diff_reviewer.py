"""Git diff审查SubAgent类型实现，包含专用插件。"""

from typing import TYPE_CHECKING
import asyncio
import logging
import os
import subprocess

from linhai.agent.base import RuntimeMessage
from linhai.agent.plugin import Plugin
from linhai.subagent.main import SubAgent
from linhai.subagent import SubAgentManager
from linhai.utils import CliRuntimeNotice, generate_id
from linhai.llm import Answer, ChatMessage
from .prompts import GIT_DIFF_REVIEWER_PROMPT

if TYPE_CHECKING:
    import linhai.agent

logger = logging.getLogger(__name__)


class GitDiffReviewerSubAgent(SubAgent):
    """Git diff审查SubAgent。"""

    def __init__(
        self,
        name: str,
        task_message: str,
        llm,
        group_chat,
        max_answer_times: int | None,
        initial_messages=None,
    ):
        super().__init__(  # type: ignore
            agent_type="git_diff_reviewer",
            name=name,
            task_message=task_message,
            llm=llm,
            group_chat=group_chat,
            max_answer_times=max_answer_times,
            initial_messages=initial_messages,
        )

    def get_system_message_prompt(self) -> str:
        """返回Git diff审查专用的系统消息prompt。"""
        import json
        from linhai.tool.base import to_tools_info

        tools_json = json.dumps(
            to_tools_info(self.toolset.get_tools()),
            ensure_ascii=False,
        )
        return GIT_DIFF_REVIEWER_PROMPT.replace("{|TOOLS|}", tools_json)

    async def _handle_execution_cycle(self) -> bool:
        result = await super()._handle_execution_cycle()
        self.messages.append(
            RuntimeMessage(
                """
请按照以下要求回复agent:

- 如果agent说某个功能因为改动太大等原因不需要在现在更改，质问“这是用户自己的要求还是你编造的？”，并要求“立即修改！”
- 如果agent说某个修改会破坏前向兼容性，质问“这会修改外部行为吗？必须重构内部函数！”
"""
            )
        )
        return result


class GitDiffReviewPlugin(Plugin):
    """在Agent使用#LINHAI_WAITING_USER且当前目录是git仓库时启动git diff审查的Plugin。"""

    FILE_MODIFICATION_TOOLS: set[str] = {
        "write_file",
        "replace_file_content",
        "append_file",
        "modify_file_with_sed",
        "insert_at_line",
    }

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self._last_git_diff: str | None = None
        self._last_new_files_content: str | None = None
        self._last_deleted_files_list: str | None = None
        self._agent_used_file_modification_tools: bool = False

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

    def _read_single_file_content(self, filename: str) -> str | None:
        """读取单个文件内容，返回格式化字符串或None（如果跳过）。"""
        # 跳过文件夹路径，确保不尝试读取文件夹
        if os.path.isdir(filename):
            return None

        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            return f"**新增文件: {filename}**\n```\n{content}\n```"
        except (OSError, UnicodeDecodeError):
            return f"**新增文件: {filename}**\n(无法读取文件内容)"

    def _get_new_files_content(self) -> str | None:
        """获取新增文件的内容，使用git ls-files来尊重.gitignore。"""
        if not os.path.exists(".git"):
            return None

        try:
            # 获取所有未跟踪且未被忽略的文件（包括文件夹中的文件）
            result = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"],
                capture_output=True,
                text=True,
                check=True,
            )
            files = result.stdout.strip().split("\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

        new_files_content = []
        for filename in files:
            if not filename:  # 跳过空行
                continue
            content = self._read_single_file_content(filename)
            if content:
                new_files_content.append(content)

        return "\n\n".join(new_files_content)

    def _get_deleted_files_list(self) -> str | None:
        """获取删除文件的列表，包括暂存区和工作区删除。"""
        if not os.path.exists(".git"):
            return None

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            status_lines = result.stdout.strip().split("\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

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
            return "**删除文件列表:**\n" + "\n".join(
                f"- {filename}" for filename in deleted_files
            )
        return ""

    async def before_waiting_user(self, agent: "linhai.agent.Agent"):
        """在Agent进入等待用户状态前检查是否需要启动git diff审查。"""
        subagent_manager = self.group_chat.get_members(
            "subagent_manager", SubAgentManager
        )

        git_diff = self._get_git_diff()
        if git_diff is None:
            return

        new_files_content = self._get_new_files_content()
        deleted_files_list = self._get_deleted_files_list()

        # 检查是否与上一次完全相同
        if (
            self._last_git_diff == git_diff
            and self._last_new_files_content == new_files_content
            and self._last_deleted_files_list == deleted_files_list
        ):
            no_change_msg = CliRuntimeNotice(
                level="INFO",
                content="未触发SubAgent审核：检测到与上一次完全相同的git更改，无需重复审查",
            )
            await self.group_chat.send_if_exists("ui_log", no_change_msg)
            return

        # 检查Agent是否使用了文件修改工具
        if not self._agent_used_file_modification_tools:
            no_relevant_msg = CliRuntimeNotice(
                level="WARNING",
                content="未触发SubAgent审核：Agent没有使用文件修改工具",
            )
            await self.group_chat.send_if_exists("ui_log", no_relevant_msg)
            return

        # 更新缓存
        self._last_git_diff = git_diff
        self._last_new_files_content = new_files_content
        self._last_deleted_files_list = deleted_files_list

        interrupt_msg = CliRuntimeNotice(
            level="INFO", content="检测到未提交的更改，启动Git diff审查SubAgent"
        )
        await self.group_chat.send_if_exists("ui_log", interrupt_msg)

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

        task_message = f"""# Git Diff审查任务

请审查以下git diff内容，检查代码变更是否符合要求：

```diff
{full_diff_content}
```

请根据系统提示中的要求进行审查，发现问题时使用request_clarification工具质问。"""

        asyncio.create_task(
            subagent_manager.create_subagent(
                agent_type="git_diff_reviewer",
                name=generate_id("git_diff_reviewer"),
                task_message=task_message,
                max_answer_times=5,
                initial_messages=user_messages,
            )
        )

    async def after_message_generation(
        self, _answer: Answer, _full_response: str, tool_calls: list[dict]
    ):
        """在Agent生成消息后记录使用的工具。"""
        if any(
            tool_call.get("name") in self.FILE_MODIFICATION_TOOLS
            for tool_call in tool_calls
        ):
            self._agent_used_file_modification_tools = True

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到before_waiting_user回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
        lifecycle.register_before_waiting_user(self.before_waiting_user)
