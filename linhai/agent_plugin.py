"""Plugin系统，用于模块化Agent的各种功能。"""

from abc import ABC, abstractmethod
from linhai.agent_base import RuntimeMessage, WAITING_USER_MARKER


class Plugin(ABC):
    """Plugin基类，定义统一的Plugin接口。"""

    @abstractmethod
    def register(self, lifecycle) -> None:
        """将Plugin注册到Lifecycle中。"""


class WaitingUserPlugin(Plugin):
    """等待用户标记检查Plugin。"""

    async def after_message_generation(self, agent, answer, full_response, tool_calls):
        """检查等待用户标记的位置。"""
        if WAITING_USER_MARKER in full_response:
            last_line = full_response.strip().rpartition("\n")[2]
            if WAITING_USER_MARKER not in last_line:
                agent.messages.append(
                    RuntimeMessage(
                        f"{WAITING_USER_MARKER!r}不在最后一行，暂停自动运行失败"
                    )
                )
            agent.state = "waiting_user"

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


class MarkerValidationPlugin(Plugin):
    """综合验证Plugin。"""

    async def after_message_generation(self, agent, answer, full_response, tool_calls):
        """检查是否同时调用工具和等待用户。"""
        if not agent.current_disable_waiting_user_warning:
            if tool_calls and WAITING_USER_MARKER in full_response:
                agent.messages.append(
                    RuntimeMessage(
                        f"错误：你既调用了工具又使用了{WAITING_USER_MARKER!r}等待用户回答，"
                        f"工具调用和等待用户是互斥的，请只选择其中一种方式"
                    )
                )
            elif agent.state == "working" and not tool_calls:
                agent.messages.append(
                    RuntimeMessage(
                        f"警告：你既没有调用工具，也没有使用{WAITING_USER_MARKER!r}等待用户回答（没有识别到工具调用），"
                        f"你需要使用{WAITING_USER_MARKER!r}等待用户回答，否则你收不到用户的消息"
                    )
                )

    def register(self, lifecycle):
        """注册到after_message_generation回调。"""
        lifecycle.register_after_message_generation(self.after_message_generation)


def register_default_plugins(lifecycle) -> None:
    """注册默认的Plugin。"""
    plugins = [
        WaitingUserPlugin(),
        MarkerValidationPlugin(),
    ]

    for plugin in plugins:
        plugin.register(lifecycle)
