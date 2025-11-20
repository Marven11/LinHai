"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod
from .base import RuntimeMessage, WAITING_USER_MARKER
from linhai.llm import Answer, ChatMessage
import linhai.agent as linhai_agent
import random
import re


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    def __init__(self, group_chat):
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

        # 检查是否同时调用工具和等待用户
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

        # 如果存在等待用户标记，检查位置并设置状态
        if has_waiting_marker:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            else:
                # 所有检查通过，设置等待用户状态
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

    async def during_message_generation(
        self, _answer: Answer, current_content: str
    ) -> bool:
        agent = self.group_chat.get_members("agent", linhai_agent.Agent)
        agent_messages = [
            msg
            for msg in agent.message_processor.get_messages()
            if isinstance(msg, ChatMessage) and msg.role == "assistant"
        ]
        is_start_message = len(agent_messages) <= 2
        if not is_start_message:
            return False
        pattern = r"```\n+```json toolcall"
        tool_call_count = current_content.count("```json toolcall")
        has_no_reason = re.search(pattern, current_content) is not None
        if tool_call_count > 1 and has_no_reason:
            agent.message_processor.append_message(
                RuntimeMessage(
                    "你需要在两个code block中间输出上下两个工具调用可以同时进行的原因！\n"
                    + self.example
                )
            )
            await agent.interrupt("错误：必须同时调用工具且在中间加上原因！")
            return True
        return False

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

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
        lifecycle.register_during_message_generation(self.during_message_generation)


class MarkdownSyntaxPlugin(Plugin):
    """Markdown语法检查Plugin。"""

    async def after_message_generation(
        self, _answer: Answer, full_response, _tool_calls
    ):
        """检查markdown语法是否正确。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)
        # 计算代码块分隔符的数量
        code_block_count = full_response.count("```")
        if code_block_count % 2 != 0:
            agent.message_processor.append_message(
                RuntimeMessage("输出markdown语法有误，可能会导致工具调用无效")
            )

    def register(self, lifecycle: "linhai_agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class GuideMinimaxPlugin(Plugin):
    """禁止minimax m2疯狂调用工具的插件"""

    async def during_message_generation(
        self, answer: Answer, current_content: str  # pylint: disable=unused-argument
    ):
        from linhai.agent import Agent
        from linhai.llm import OpenAi

        agent = self.group_chat.get_members("agent", Agent)
        model = await agent.get_current_model()
        if not isinstance(model, OpenAi) or model.compatibility != "minimax":
            return False

        if current_content.count("```json toolcall") > 5:
            await agent.interrupt("错误：你现在是Minimax，禁止使用超过5个工具！")
            return True
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
        # 正则表达式匹配：一行中有<｜end▁of▁[a-z]+｜>，且前面都是汉字（不限制标记位置）
        pattern = r"^[\u4e00-\u9fffa-zA-Z0-9.,，。！？；：《》（）【】、…]+<｜end▁of▁[a-z]+｜>"

        # 检查每一行
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

        # 检查每一行是否只有'</think>'
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

        # 检查是否启用了目录更改检测
        enable_directory_change_detection = agent.context.get(
            "enable_directory_change_detection", False
        )
        if not enable_directory_change_detection:
            return

        current_directory = Path.cwd().resolve()

        # 如果目录没有变化，直接返回
        if self.last_directory == current_directory:
            return

        # 更新目录记录
        self.last_directory = current_directory

        # 检查特定文件
        target_files = ["LINHAI.md", "AGENTS.md", "CLAUDE.md"]
        for filename in target_files:
            filepath = current_directory / filename
            if filepath.exists():
                # 检查是否已经存在相同路径的GlobalMemory或PathMemory
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
        self, _answer: Answer, _full_response: str, tool_calls
    ):
        """检查是否连续多次只调用了一个工具。"""
        from linhai.agent import Agent

        agent = self.group_chat.get_members("agent", Agent)

        # 检查tool_calls长度是否为1
        if len(tool_calls) == 1:
            self.single_tool_call_count += 1

            # 如果连续5次都只调用1个工具，提醒agent
            if self.single_tool_call_count >= 5:
                agent.message_processor.append_message(
                    RuntimeMessage(
                        f"注意：你连续{self.single_tool_call_count}次仅调用一个工具，"
                        "除开特殊原因不要每次只调用一个工具！"
                    )
                )
        else:
            # 重置计数器
            self.single_tool_call_count = 0

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

        agent = self.group_chat.get_members("agent", Agent)

        # 检查是否是第一个回复：消息历史中没有之前的agent消息
        has_previous_agent_message = any(
            msg.role == "assistant"
            for msg in agent.message_processor.get_messages()
            if hasattr(msg, "role")
        )

        # 如果是第一个回复且有一行的开头是`**tool**`，则打断
        if not has_previous_agent_message:
            # 检查是否有一行的开头是`**tool**`
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
