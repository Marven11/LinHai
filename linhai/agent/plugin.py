"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod
from typing import Any
import asyncio
import logging
import shlex
import os

from .base import RuntimeMessage, WAITING_USER_MARKER
from ..llm import Answer, ToolCallMessage
from ..utils import CliRuntimeNotice
import linhai.agent as linhai_agent
from linhai.group_chat import GroupChat
from linhai.utils import generate_id
import linhai.subagent as linhai_subagent
import re

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat

    @abstractmethod
    def register(self, lifecycle) -> None:
        """将Plugin注册到Lifecycle中。"""


class WaitingUserPlugin(Plugin):
    """等待用户标记检查Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response, tool_calls
    ):
        """检查等待用户标记的位置和工具调用冲突。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        has_waiting_marker = WAITING_USER_MARKER in full_response

        if not agent.current_disable_waiting_user_warning:
            if tool_calls and has_waiting_marker:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                        f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                    )
                )
                return
            if agent.state == "working" and not tool_calls and not has_waiting_marker:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"警告：你既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用），"
                        f"你需要使用{WAITING_USER_MARKER!r}等待用户回答，否则你收不到用户的消息"
                    )
                )
                return

        if has_waiting_marker:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            else:
                agent.state = "waiting_user"

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class WrongEndPlugin(Plugin):
    """禁止输出end of sentence的plugin"""

    async def after_message_generation(
        self,
        _answer: Answer,
        full_response: str,
        _tool_calls,
    ):
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        regex_result = re.search("<｜end▁of▁[a-z]+｜>", full_response)
        if regex_result:
            agent.message_processor.append_message(
                RuntimeMessage(f"警告: 输出了错误的token: {regex_result!r}")
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class BadMultiToolCall(Plugin):
    """检查多工具调用原因插件。

    意图：
    1. 模型输出错误时提醒（多个工具调用块之间没有文字内容）
    2. 模型修复，接下来正确输出则提醒输出正确（从没有原因到有原因时）

    通过检测工具调用块之间是否有任何文字内容来判断是否有原因，而不是依赖特定关键词。
    """

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.last_message_had_reason = True
        self.example = """
例如，当你需要同时调用多个工具时，应该这样输出（用箭头标记了你应该输出的部分）：

我将开始探索当前代码仓库，首先是列出当前文件夹

```json toolcall
{"name": "list_files", "arguments": {"dirpath": "."}}
```

同时调用：然后读取example.txt # <--- 这是你漏掉的“同时调用的原因”

```json toolcall
{"name": "read_file", "arguments": {"filepath": "./example.txt"}}
```"""

    async def after_message_generation(
        self,
        _answer: Answer,
        full_response: str,
        _tool_calls,
    ):
        agent = self.group_chat.get_members("agent", linhai_agent.Agent)

        tool_call_count = full_response.count("```json toolcall")

        pattern = r"```\n+```json toolcall"
        has_no_reason = re.search(pattern, full_response) is not None

        if tool_call_count > 1 and has_no_reason:

            agent.message_processor.append_message(
                RuntimeMessage(
                    "警告：你是不是忘记在多个工具调用之间输出可以同时调用的原因了？\n"
                    "你需要在两个code block中间输出上下两个工具调用可以同时进行的原因！\n"
                    + self.example
                )
            )
            self.last_message_had_reason = False
        elif tool_call_count > 1 and not has_no_reason:
            if not self.last_message_had_reason:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        "你成功输出了'同时调用的原因'，以后注意在同时调用工具时都要输出原因"
                    )
                )
            self.last_message_had_reason = True
        if re.search(r"```\n+[^\n]+<---[^\n]+\n+```json toolcall", pattern) is not None:
            agent.message_processor.append_message(
                RuntimeMessage("不要在原因中加上箭头！")
            )
        if (
            re.search(r"```\n+[^\n]+同时调用：[^\n]+\n+```json toolcall", pattern)
            is not None
        ):
            agent.message_processor.append_message(
                RuntimeMessage("不需要在原因中加上“同时调用：”，很丑")
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class StopFastAgentPlugin(Plugin):
    """禁止minimax m2/glm 4.6疯狂调用工具的插件"""

    MAX_TOOLCALL_COUNT = 5

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.speeding_counter = 0

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """在消息生成前检查目录是否更改。"""
        from linhai.agent import Agent
        from linhai.llm import OpenAi, ChatMessage

        agent = self.group_chat.get_members("agent", Agent)

        has_previous_agent_message = any(
            msg.role == "assistant"
            for msg in agent.message_processor.get_messages()
            if isinstance(msg, ChatMessage)
        )
        if not has_previous_agent_message:
            return

        model = await agent.get_current_model()
        if not isinstance(model, OpenAi) or model.compatibility not in [
            "minimax",
            "glm",
        ]:
            return False
        agent.message_processor.append_message(
            RuntimeMessage(
                f"你现在是{model.compatibility}，必须在调用工具前仔细思考，禁止调用超过{self.MAX_TOOLCALL_COUNT}个工具！"
            )
        )
        if model.compatibility == "glm":
            agent.message_processor.append_message(
                RuntimeMessage("你现在是GLM，必须打开思考模式，仔细思考！")
            )

    async def during_message_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        from linhai.agent import Agent
        from linhai.llm import OpenAi

        agent = self.group_chat.get_members("agent", Agent)
        model = await agent.get_current_model()
        if not isinstance(model, OpenAi) or model.compatibility not in [
            "minimax",
            "glm",
        ]:
            return False

        if current_content.count("```json toolcall") > self.MAX_TOOLCALL_COUNT:
            extra_message = ""
            if self.speeding_counter:
                extra_message = (
                    "从刚刚开始就一直在调用大量工具，你疯了？？？？"
                    + "？！？！" * self.speeding_counter
                )
            await agent.interrupt(
                f"禁止超速：你现在是{model.compatibility}，禁止使用超过{self.MAX_TOOLCALL_COUNT}个工具！"
                + extra_message
            )
            self.speeding_counter += 1
            return True
        self.speeding_counter = 0
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class WeirdEndOfSentencePlugin(Plugin):
    """错误结束标记检查Plugin。"""

    async def during_message_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """检查是否有一行内容有`<｜end▁of▁[a-z]+｜>`且前面都是汉字。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        pattern = r"^[\u4e00-\u9fffa-zA-Z0-9.,，。！？；：《》（）【】、…]+<｜end▁of▁[a-z]+｜>"

        for line in current_content.split("\n"):
            if re.search(pattern, line):
                await agent.interrupt(
                    "检测到错误结束标记：在一行中有`<｜end▁of▁[a-z]+｜>`且前面都是文字，已打断输出"
                )
                return True
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class EndThinkPlugin(Plugin):
    """检查输出中是否有只有'</think>'的行并打断agent。"""

    async def during_message_generation(self, _answer: Answer, current_content: str):
        """检查是否有一行只有'</think>'。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        lines = current_content.split("\n")
        for line in lines:
            if line.strip() == "</think>":
                await agent.interrupt(
                    "错误：检测到只有'</think>'的行，你将两条消息合并成了一条发送！请依次发送每条消息！"
                )
                return True
        return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class DirectoryChangePlugin(Plugin):
    """目录更改检测插件，检测当前目录更改并检查特定文件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.last_directory = None

    async def before_message_generation(
        self, _enable_compress: bool, _disable_waiting_user_warning: bool
    ):
        """在消息生成前检查目录是否更改。"""
        from linhai.agent.main import Agent
        from linhai.agent.base import GlobalMemory, PathMemory
        from pathlib import Path

        agent = self.group_chat.get_members("agent", Agent)

        enable_directory_change_detection = agent.context.get(
            "enable_directory_change_detection", False
        )
        if not enable_directory_change_detection:
            return

        current_directory = Path.cwd().resolve()

        if self.last_directory == current_directory:
            return

        self.last_directory = current_directory

        target_files = ["LINHAI.md", "AGENTS.md", "CLAUDE.md"]
        for filename in target_files:
            filepath = current_directory / filename
            if filepath.exists():

                has_duplicate = any(
                    message.filepath.resolve() == filepath.resolve()
                    for message in agent.message_processor.get_messages()
                    if isinstance(message, (GlobalMemory, PathMemory))
                )
                if not has_duplicate:
                    agent.message_processor.append_message(PathMemory(filepath))

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到before_message_generation回调。"""
        lifecycle.register_before_message_generation(self.before_message_generation)


class SingleToolCallReminderPlugin(Plugin):
    """提醒agent不要连续多次只调用单个工具的插件。"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.single_tool_call_count = 0

    async def after_message_generation(
        self, _answer: Answer, _full_response: str, tool_calls: list[dict]
    ):
        """检查是否连续多次只调用了一个工具。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        if len(tool_calls) == 1:
            self.single_tool_call_count += 1

            if self.single_tool_call_count >= 2:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"注意：你连续{self.single_tool_call_count}次仅调用一个工具，"
                        "除开特殊原因不要每次只调用一个工具！"
                        + "！！！" * self.single_tool_call_count
                    )
                )
        else:
            self.single_tool_call_count = 0

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class ClarificationCheckPlugin(Plugin):
    """提醒agent需要立马回复clarification的工具"""

    def __init__(self, group_chat):
        super().__init__(group_chat)
        self.without_clarification_counter = 0

    async def after_message_generation(
        self, _answer: Answer, _full_response: str, tool_calls: list[dict]
    ):
        """检查是否连续多次只调用了一个工具。"""
        from linhai.clarification import ClarificationManager
        from linhai.agent import Agent

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        agent = self.group_chat.get_members("agent", Agent)

        if clarification_manager.has_unanswered_clarifications() and all(
            item.get("name") != "respond_clarification" for item in tool_calls
        ):
            self.without_clarification_counter += 1

            if self.without_clarification_counter >= 2:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"注意：你连续{self.without_clarification_counter}次没有回复Clarification，"
                        "你需要立即回复！"
                        + "！！！" * self.without_clarification_counter
                    )
                )
        else:
            self.without_clarification_counter = 0

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class PreventToolOutputPlugin(Plugin):
    """防止agent错误输出工具调用内容的插件。

    当agent的第一个回复中有一行的开头是`**tool**`时打断agent，
    并提示不要输出工具调用的内容。
    """

    async def during_message_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        """在消息生成过程中检查是否错误输出了工具调用内容。"""
        from linhai.agent import Agent
        from linhai.llm import ChatMessage

        agent = self.group_chat.get_members("agent", Agent)

        has_previous_agent_message = any(
            msg.role == "assistant"
            for msg in agent.message_processor.get_messages()
            if isinstance(msg, ChatMessage)
        )

        if not has_previous_agent_message:

            lines = current_content.split("\n")
            for line in lines:
                if line.strip().startswith("**tool**"):
                    await agent.interrupt(
                        "错误：请不要输出工具调用的内容！"
                        "工具调用内容（如`**tool**`）是系统内部使用的标签，"
                        "你不应该直接输出这些内容。"
                    )
                    return True

        return False

    def register(self, lifecycle):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class ClarificationBlockingPlugin(Plugin):
    """阻止Agent在有未解答澄清时停下等待用户的Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response: str, _tool_calls
    ):
        """检查是否有未解答的澄清，如果有则阻止使用等待用户标记。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.clarification import ClarificationManager

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
                        "请先回复所有SubAgent的澄清问题。"
                    )
                )
                agent.state = "working"

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class SubAgentCollaborationPlugin(Plugin):
    """基于lifecycle事件驱动subagent协作的Plugin。

    在工具失败、工具冲突时启动subagent，检查agent是否违反了多个工具的调用规则。
    """

    async def tool_failure(
        self,
        agent: "linhai_agent.Agent",
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
        agent: "linhai_agent.Agent",
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
        subagent_manager: "linhai_subagent.SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        error: Any,
    ) -> None:
        """在后台任务中检查agent是否违反规则。"""
        from linhai.agent import Agent

        from linhai.prompt import SUBAGENT_CHECKLIST

        tool_rules = SUBAGENT_CHECKLIST

        task_message = f"""你是一名规则检查员，负责检查Agent的工具调用是否违反规则。

**Agent的当前完整回答:**
```
{full_response}
```

**失败的工具调用详情:**
- 工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 错误信息: {error}

**你的任务:**
仔细检查Agent的上述回答，判断其是否违反了以下任何一条规则。如果违反，必须调用request_clarification向Agent提出澄清问题。

**工具调用规则:**
{tool_rules}

**执行步骤:**

1. 逐一检查上述每条规则
2. 如果发现任何违反，调用request_clarification工具，提问格式:
"规则违反: [规则名称]。在Agent的回答中，你[具体违反行为]。请解释为什么要这样做？"

3. 如果没有发现任何违反，调用exit工具退出，原因写"未发现规则违反"

**重要:** 你必须严格按上述规则检查，不能遗漏任何一条。如果发现问题，必须提出澄清。"""

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    async def _check_conflict_violations(
        self,
        subagent_manager: "linhai_subagent.SubAgentManager",
        full_response: str,
        tool_call: ToolCallMessage,
        conflicting_tools: list[str],
    ) -> None:
        """在后台任务中检查agent是否违反规则（工具冲突情况）。"""
        from linhai.agent import Agent

        from linhai.prompt import SUBAGENT_CHECKLIST

        tool_rules = SUBAGENT_CHECKLIST

        task_message = f"""你是一名规则检查员，负责检查Agent的工具调用是否违反规则。

**Agent的当前完整回答:**
```
{full_response}
```

**工具冲突详情:**
- 冲突工具名称: {tool_call.function_name}
- 工具参数: {tool_call.function_arguments}
- 与以下工具冲突: {', '.join(conflicting_tools)}

**你的任务:**
仔细检查Agent的上述回答，判断其是否违反了以下任何一条规则。如果违反，必须调用request_clarification向Agent提出澄清问题。

**工具调用规则:**
{tool_rules}

**执行步骤:**

1. 逐一检查上述每条规则
2. 如果发现任何违反，调用request_clarification工具，提问格式:
"规则违反: [规则名称]。在Agent的回答中，你[具体违反行为]。请解释为什么要这样做？"

3. 如果没有发现任何违反，调用exit工具退出，原因写"未发现规则违反"

**重要:** 你必须严格按上述规则检查，不能遗漏任何一条。如果发现问题，必须提出澄清。"""

        await subagent_manager.create_subagent(
            agent_type="violation_checker",
            name=generate_id("violation_subagent"),
            task_message=task_message,
            max_answer_times=1,
        )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到lifecycle回调。"""
        lifecycle.register_tool_failure(self.tool_failure)
        lifecycle.register_tool_conflict(self.tool_conflict)


class GitBlockingPlugin(Plugin):
    """阻止Agent在有未解答澄清时使用git命令的Plugin。"""

    async def before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        """检查是否有未解答的澄清，如果有则阻止使用git命令。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        from linhai.clarification import ClarificationManager

        clarification_manager = self.group_chat.get_members(
            "clarification_manager", ClarificationManager
        )
        if (
            clarification_manager
            and clarification_manager.has_unanswered_clarifications()
        ):

            tool_name = tool_call.function_name
            arguments = tool_call.function_arguments

            if tool_name in ["run_simple_command", "run_complex_command"]:
                command = arguments.get("command", "")

                if self._is_git_command(command):
                    agent.message_processor.append_message(
                        RuntimeMessage(
                            f"错误：有未解答的澄清问题，禁止使用git命令。"
                            f"命令 '{command}' 被识别为git命令，请先回复所有SubAgent的澄清问题。"
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
        except Exception:
            return False

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到before_tool_call回调。"""
        lifecycle.register_before_tool_call(self.before_tool_call)


class ClarificationWaitingUserPlugin(Plugin):
    """阻止Agent在有未解答澄清时进入等待用户状态的Plugin。"""

    async def before_waiting_user(self, agent: "linhai_agent.Agent"):
        """检查是否有未解答的澄清，如果有则阻止进入等待用户状态。"""

        from linhai.clarification import ClarificationManager

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

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到before_waiting_user回调。"""
        lifecycle.register_before_waiting_user(self.before_waiting_user)
