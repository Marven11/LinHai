"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod
from linhai.agent_base import RuntimeMessage, WAITING_USER_MARKER
from linhai.llm import Answer
import linhai
import re


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    @abstractmethod
    def register(self, lifecycle) -> None:
        """将Plugin注册到Lifecycle中。"""


class WaitingUserPlugin(Plugin):
    """等待用户标记检查Plugin。"""

    async def after_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, full_response, tool_calls
    ):
        """检查等待用户标记的位置和工具调用冲突。"""
        has_waiting_marker = WAITING_USER_MARKER in full_response

        # 检查是否同时调用工具和等待用户
        if not agent.current_disable_waiting_user_warning:
            if tool_calls and has_waiting_marker:
                agent.messages.append(
                    RuntimeMessage(
                        f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                        f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                    )
                )
                return
            if agent.state == "working" and not tool_calls and not has_waiting_marker:
                agent.messages.append(
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
                agent.messages.append(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            else:
                # 所有检查通过，设置等待用户状态
                agent.state = "waiting_user"

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class ToolcallWithoutPlanningPlugin(Plugin):
    """工具调用量检查Plugin。"""

    async def during_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, current_content: str
    ):
        """检查工具调用量是否超过限制。"""
        json_block_count = current_content.count("\n```json toolcall")
        pattern = r"^ *- \[[ x]\]"
        planning_count = len(re.findall(pattern, current_content, re.MULTILINE))

        if json_block_count > 1 and planning_count == 0:
            await agent.group_chat.send("cli_user_output", answer)
            agent.messages.append(
                RuntimeMessage(
                    "错误：你没有使用`- [ ]`和`- [x]`进行计划就调用了多个工具，检查你的行为！"
                )
            )
            answer.interrupt()
            return True

        return False

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class ToolCallCountPlugin(Plugin):
    """工具调用量检查Plugin。"""

    async def during_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, current_content: str
    ):
        """检查工具调用量是否超过限制。"""
        json_block_count = current_content.count("\n```json toolcall")

        content_length = len(current_content)
        if content_length < 8000:
            max_json_blocks = 30
        else:
            max_json_blocks = 1

        if json_block_count > max_json_blocks:
            await agent.group_chat.send("cli_user_output", answer)
            agent.messages.append(
                RuntimeMessage(
                    f"错误：禁止在超长回答中调用巨量工具。"
                    f"一次性调用了超过{max_json_blocks}个工具，当前回答长度{content_length}字符，"
                    f"最多允许{max_json_blocks}个工具调用。请分多次调用。"
                )
            )
            answer.interrupt()
            return True

        return False

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class WrongEndPlugin(Plugin):
    """禁止输出end of sentence的plugin"""

    async def after_message_generation(
        self,
        agent: "linhai.agent.Agent",
        answer: Answer,
        full_response: str,
        tool_calls,
    ):
        regex_result = re.search("<｜end▁of▁[a-z]+｜>", full_response)
        if regex_result:
            agent.messages.append(
                RuntimeMessage(f"警告: 输出了错误的token: {regex_result!r}")
            )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class BadMultiToolCall(Plugin):
    """检查多工具调用原因"""

    def __init__(self):
        self.last_message_had_reason = True

    async def after_message_generation(
        self,
        agent: "linhai.agent.Agent",
        answer: Answer,
        full_response: str,
        tool_calls,
    ):
        # 检查是否有连续工具调用块
        pattern = r"```\n+```json toolcall"
        if re.search(pattern, full_response) and full_response.count("```json toolcall") > 1:
            agent.messages.append(
                RuntimeMessage(
                    "警告：你是不是忘记在多个工具调用之间输出可以同时调用的原因了？"
                )
            )
            self.last_message_had_reason = False
        elif not self.last_message_had_reason and full_response.count("```json toolcall") > 1:
            agent.messages.append(
                RuntimeMessage(
                    "你成功输出了'同时调用的原因'，以后注意在同时调用工具时都要输出原因"
                )
            )
            self.last_message_had_reason = True

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class ThinkingToolCallPlugin(Plugin):
    """禁止过度思考工具调用plugin"""

    async def during_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, current_content: str
    ):
        """检查工具调用量是否超过限制。"""
        current_reasoning_content = answer.get_reasoning_message()
        if current_reasoning_content is None:
            return False
        json_block_count = current_reasoning_content.count("\n```json toolcall")

        max_json_blocks = 2

        if json_block_count > max_json_blocks:
            await agent.group_chat.send("cli_user_output", answer)
            agent.messages.append(
                RuntimeMessage(
                    f"错误：大量思考如何使用```json toolcall调用工具，输出```json toolcall超过{max_json_blocks}次"
                    "，你只能（且应该）在实际输出时调用多个工具！"
                )
            )
            answer.interrupt()
            return True

        return False

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class ExcessiveCheckmarkPlugin(Plugin):
    """检查过多完成标记的Plugin。"""

    async def after_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, full_response, tool_calls
    ):
        """检查是否输出了过多的- [x]标记。"""
        count = full_response.count("- [x]")
        if count > 10:  # 阈值设为10
            agent.messages.append(
                RuntimeMessage(
                    f"警告：你输出了过多`- [x]`标记（{count}个），请使用分级无序列表整理大小任务。"
                    "请注意：如果完成的任务过多，可以不输出完成的小任务，只输出大任务已完成。"
                    "提示：如果完成的任务过多（十几条），在所有小任务都完成时，可以不输出完成的小任务，只输出大任务已完成。因为小任务是过程性的，完成的细节相对于结果来说不重要。"
                )
            )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class MarkdownSyntaxPlugin(Plugin):
    """Markdown语法检查Plugin。"""

    async def after_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, full_response, tool_calls
    ):
        """检查markdown语法是否正确。"""
        # 计算代码块分隔符的数量
        code_block_count = full_response.count("```")
        if code_block_count % 2 != 0:
            agent.messages.append(
                RuntimeMessage("输出markdown语法有误，可能会导致工具调用无效")
            )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class TaskPlanningPlugin(Plugin):
    """任务规划格式检查Plugin。"""

    def __init__(self):
        self.no_planning_score = 0

    async def during_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, current_content: str
    ):
        """检查工具调用量是否超过限制。"""
        if self.no_planning_score <= 3:
            return
        current_reasoning_content = answer.get_reasoning_message()
        if current_reasoning_content is None:
            return False
        pattern = r"^ *- \[[ x]\]"
        matches = re.findall(pattern, current_content, re.MULTILINE)
        if not matches:
            return False
        json_block_count = current_reasoning_content.count("\n```json toolcall")
        if json_block_count == 0:
            return False
        agent.messages.append(
            RuntimeMessage(
                "错误：你已经连续多次忘记任务规划，你的工具调用已经被打断。"
                "你必须在工具调用前补上任务规划！"
            )
        )
        answer.interrupt()
        return True

    async def after_message_generation(
        self, agent: "linhai.agent.Agent", answer: Answer, full_response, tool_calls
    ):
        """检查是否输出了任务规划格式（- [ ] 或 - [x]）。"""

        # 使用正则匹配每一行开头的任务规划标记
        pattern = r"^ *- \[[ x]\]"
        matches = re.findall(pattern, full_response, re.MULTILINE)

        # 如果没有找到任何任务规划标记，则提醒
        if not matches:
            self.no_planning_score += 1
            agent.messages.append(
                RuntimeMessage(
                    (
                        "注意：你没有输出任务规划"
                        if self.no_planning_score == 1
                        else f"【注意】：你已累计{self.no_planning_score}次没有输出任务规划，"
                        "超过3次则会被强制暂停，直到你输出任务规划为止才能继续！"
                    )
                    + "请使用`- [ ]`或`- [x]`进行任务规划"
                    + "！" * (self.no_planning_score - 1) * 3
                )
            )
            reasoning_content = answer.get_reasoning_message()
            if reasoning_content is not None and re.findall(
                pattern, reasoning_content, re.MULTILINE
            ):
                agent.messages.append(
                    RuntimeMessage(
                        "注意：你刚刚在思考时输出了任务规划，但是没有在实际的输出中输出！"
                        "必须在实际的输出而非只有思考时输出任务规划！"
                    )
                )
        elif self.no_planning_score > 0:
            self.no_planning_score -= 1
            agent.messages.append(
                RuntimeMessage(
                    "成功输出任务规划，抵消一次错误输出，之后一定要注意任务规划"
                )
            )

    def register(self, lifecycle: "linhai.agent.Lifecycle"):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


def register_default_plugins(lifecycle) -> None:
    """注册默认的Plugin。"""
    plugins = [
        WaitingUserPlugin(),
        ToolcallWithoutPlanningPlugin(),
        ToolCallCountPlugin(),
        WrongEndPlugin(),
        BadMultiToolCall(),
        ExcessiveCheckmarkPlugin(),
        MarkdownSyntaxPlugin(),
        ThinkingToolCallPlugin(),
        TaskPlanningPlugin(),
    ]

    for plugin in plugins:
        plugin.register(lifecycle)
