"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod
from linhai.agent_base import RuntimeMessage, WAITING_USER_MARKER
from linhai.llm import Answer


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    @abstractmethod
    def register(self, lifecycle) -> None:
        """将Plugin注册到Lifecycle中。"""


class WaitingUserPlugin(Plugin):
    """等待用户标记检查Plugin。"""

    async def after_message_generation(
        self, agent, answer: Answer, full_response, tool_calls
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

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class ToolCallCountPlugin(Plugin):
    """工具调用量检查Plugin。"""

    async def during_message_generation(self, agent, answer: Answer, current_content):
        """检查工具调用量是否超过限制。"""
        json_block_count = current_content.count("\n```json toolcall")

        content_length = len(current_content)
        if content_length < 2000:
            max_json_blocks = 5
        else:
            max_json_blocks = 1

        if json_block_count > max_json_blocks:
            await agent.user_output_queue.put(answer)
            agent.messages.append(
                RuntimeMessage(
                    f"错误：一次性调用了超过{max_json_blocks}个工具，当前回答长度{content_length}字符，"
                    f"最多允许{max_json_blocks}个工具调用。请分多次调用。"
                )
            )
            answer.interrupt()
            return True

        return False

    def register(self, lifecycle):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


class ThinkingToolCallPlugin(Plugin):
    """禁止过度思考工具调用plugin"""

    async def during_message_generation(self, agent, answer: Answer, current_content):
        """检查工具调用量是否超过限制。"""
        current_reasoning_content = answer.get_reasoning_message()
        if not isinstance(current_reasoning_content, str):
            return False
        json_block_count = current_reasoning_content.count("\n```json toolcall")

        max_json_blocks = 2

        if json_block_count >= max_json_blocks:
            await agent.user_output_queue.put(answer)
            agent.messages.append(
                RuntimeMessage(
                    f"错误：大量思考如何使用```json toolcall调用工具，输出```json toolcall超过{max_json_blocks}次，请避免过度思考如何进行工具调用"
                )
            )
            answer.interrupt()
            return True

        return False

    def register(self, lifecycle):
        """注册到during_message_generation回调。"""
        lifecycle.register_during_message_generation(self.during_message_generation)


def register_default_plugins(lifecycle) -> None:
    """注册默认的Plugin。"""
    plugins = [
        WaitingUserPlugin(),
        ToolCallCountPlugin(),
        ExcessiveCheckmarkPlugin(),
    ]

    for plugin in plugins:
        plugin.register(lifecycle)


class ExcessiveCheckmarkPlugin(Plugin):
    """检查过多完成标记的Plugin。"""

    async def after_message_generation(
        self, agent, answer: Answer, full_response, tool_calls
    ):
        """检查是否输出了过多的- [x]标记。"""
        count = full_response.count("- [x]")
        if count > 10:  # 阈值设为10
            agent.messages.append(
                RuntimeMessage(
                    f"警告：你输出了过多`- [x]`标记（{count}个），"
                    "请注意：如果完成的任务过多，可以不输出完成的小任务，只输出大任务已完成。"
                    "提示：如果完成的任务过多（十几条），在所有小任务都完成时，可以不输出完成的小任务，只输出大任务已完成。因为小任务是过程性的，完成的细节相对于结果来说不重要。"
                )
            )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)
