"""NotificationMessagePlugin类的单元测试。"""

import unittest
from unittest.mock import Mock, AsyncMock, patch

from linhai.agent.orchestration import NotificationMessagePlugin
from linhai.registry import Registry
from linhai.agent.main import Agent
from linhai.agent.message import AgentMessage
from linhai.agent.orchestration import AgentContextOrchestration
from linhai.type_hints import ThresholdInfo


class TestNotificationMessagePlugin(unittest.IsolatedAsyncioTestCase):
    """NotificationMessagePlugin类的测试用例。"""

    async def asyncSetUp(self):
        """设置测试环境。"""
        self.registry = Registry()
        self.plugin = NotificationMessagePlugin(self.registry)

        # 创建模拟的Agent和AgentContextOrchestration
        self.agent = Mock(spec=Agent)
        self.agent.get_threshold_info = Mock()
        # 添加message_processor mock
        self.agent.message_processor = Mock()
        self.agent.message_processor.update_notification_message = Mock()

        self.orchestration = Mock(spec=AgentContextOrchestration)
        self.orchestration.compute_orchestration_context = Mock(
            return_value={
                "threshold_info": None,
                "current_state": "绿灯",
                "is_dirty": False,
                "notification_message": "当前为绿灯状态, 上下文占用量为50.0%, 当前有0条大消息, 一分钟内没有调用过消息清理工具, 建议: 不要担心消息限制，立即工作",
                "tool_block_details": {
                    "blocked_category": None,
                    "actual_category": "other",
                    "is_dirty": False,
                    "current_state": "绿灯",
                },
            }
        )

        # 注册到group chat
        self.registry.register_member("agent", self.agent)
        self.registry.register_member("agent_context_orchestration", self.orchestration)

    def test_register(self):
        """测试插件注册。"""
        lifecycle = Mock()
        self.plugin.register(lifecycle)

        lifecycle.register_before_message_generation.assert_called_once_with(
            self.plugin.before_message_generation
        )


if __name__ == "__main__":
    unittest.main()
