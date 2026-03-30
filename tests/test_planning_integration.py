import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path
import asyncio

from linhai.agent.create import create_agent_build_context
from linhai.agent.planning import PlanningPromptMessage


class TestPlanningIntegration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_registry = MagicMock()
        self.mock_config = MagicMock()
        # 模拟LLM配置对象列表
        mock_llm_config = MagicMock()
        mock_llm_config.name = "test_llm"
        self.mock_config.llm = [mock_llm_config]
        # 模拟tools.secret.config_path以通过secret系统初始化
        mock_tools = MagicMock()
        mock_secret = MagicMock()
        mock_secret.config_path = "/tmp/test_secret_config.json"
        mock_tools.secret = mock_secret
        self.mock_config.tools = mock_tools
        # 模拟agent.compress_threshold
        self.mock_config.agent = MagicMock()
        self.mock_config.agent.compress_threshold = 0.9
        self.mock_config.agent.enable_directory_change_detection = False
        self.mock_config.agent.allowed_commands = None
        self.mock_config.agent.mcp = MagicMock()
        self.mock_config_basedir = Path("/tmp/test_config")
        self.mock_cli_args = MagicMock()
        self.mock_cli_args.planning = False
        self.mock_cli_args.llm = None
        self.mock_cli_args.checklist = None

    async def test_planning_parameter_default_false(self):
        # 注意：create_agent_build_context需要llm_name参数，我们通过cli_args.llm传递
        self.mock_cli_args.llm = None
        context = create_agent_build_context(
            registry=self.mock_registry,
            config=self.mock_config,
            config_basedir=self.mock_config_basedir,
            cli_args=self.mock_cli_args,
            planning=False,
        )

        self.assertFalse(context["planning"])

    async def test_planning_parameter_true(self):
        self.mock_cli_args.llm = None
        context = create_agent_build_context(
            registry=self.mock_registry,
            config=self.mock_config,
            config_basedir=self.mock_config_basedir,
            cli_args=self.mock_cli_args,
            planning=True,
        )

        self.assertTrue(context["planning"])

    async def test_create_pinned_messages_with_planning(self):
        from linhai.agent.create import _create_pinned_messages
        from linhai.agent.base import RuntimeMessage, GlobalPrompt
        from linhai.llm import SystemMessage
        from linhai.llm import UserMessage, AssistantMessage

        # 模拟对话文件夹
        mock_conversation_folder = Path("/tmp/test_conversation")
        mock_conversation_folder.mkdir(exist_ok=True)
        self.mock_registry.get_member_typechecked = MagicMock(
            side_effect=lambda name, cls=None: {
                "conversation_folder": mock_conversation_folder
            }.get(name)
        )

        # 模拟消息列表
        mock_messages = [
            SystemMessage(registry=self.mock_registry),
            GlobalPrompt(filepath=Path("/tmp/test_global_prompt.md")),
            RuntimeMessage("User message 1"),
            AssistantMessage(message="Assistant response 1"),
        ]

        context = {
            "planning": True,
            "registry": self.mock_registry,
            "cli_args": self.mock_cli_args,
            "config": self.mock_config,
            "config_basedir": self.mock_config_basedir,
            "llms": self.mock_config.llm,
            "checklist_path": None,
            "user_prompt": None,
            "max_toolcall_token_in_round": 0.3,
            "llm_name": None,
            "telegram_config": None,
        }

        # 模拟agent.message_processor.messages
        mock_agent = MagicMock()
        mock_agent.message_processor.messages = mock_messages

        with patch("linhai.agent.create.Agent", return_value=mock_agent):
            pinned_messages = await _create_pinned_messages(context)

        # 检查是否包含PlanningPromptMessage
        planning_messages = [
            msg for msg in pinned_messages if isinstance(msg, PlanningPromptMessage)
        ]

        self.assertEqual(len(planning_messages), 1)
        planning_msg = planning_messages[0]

        # 检查文件夹是否正确
        expected_folder = mock_conversation_folder / "planning"
        self.assertEqual(planning_msg.planning_folder, expected_folder)

        # 检查文件路径
        file_paths = planning_msg.get_file_paths()
        self.assertEqual(file_paths["status"], expected_folder / "STATUS.md")
        self.assertEqual(file_paths["todolist"], expected_folder / "TODOLIST.md")
        self.assertEqual(file_paths["design"], expected_folder / "DESIGN.md")

        # 检查内容是否包含路径
        content = planning_msg.message
        self.assertIn(str(expected_folder), content)
        self.assertIn("STATUS.md", content)
        self.assertIn("TODOLIST.md", content)
        self.assertIn("DESIGN.md", content)

    async def test_create_pinned_messages_without_planning(self):
        from linhai.agent.create import _create_pinned_messages

        context = {
            "planning": False,
            "registry": self.mock_registry,
            "cli_args": self.mock_cli_args,
            "config": self.mock_config,
            "config_basedir": self.mock_config_basedir,
            "llms": self.mock_config.llm,
            "checklist_path": None,
            "user_prompt": None,
            "max_toolcall_token_in_round": 0.3,
            "llm_name": None,
            "telegram_config": None,
        }

        pinned_messages = await _create_pinned_messages(context)

        # 检查是否不包含PlanningPromptMessage
        planning_messages = [
            msg for msg in pinned_messages if isinstance(msg, PlanningPromptMessage)
        ]

        self.assertEqual(len(planning_messages), 0)

    async def test_plugin_registration_with_planning_true(self):
        # 测试planning为True时插件注册逻辑
        from linhai.agent.create import create_agent_from_config

        # 创建上下文配置，planning为True
        context = {
            "planning": True,
            "registry": self.mock_registry,
            "cli_args": self.mock_cli_args,
            "config": self.mock_config,
            "config_basedir": self.mock_config_basedir,
            "llms": self.mock_config.llm,
            "checklist_path": None,
            "user_prompt": None,
            "llm_name": "test_llm",
            "max_toolcall_token_in_round": 30000,
            "toolsets_config": self.mock_config.tools.toolsets,
            "override_toolsets": self.mock_config.agent.override_toolsets,
            "compress_threshold": self.mock_config.agent.compress_threshold,
            "enable_directory_change_detection": self.mock_config.agent.enable_directory_change_detection,
            "max_toolcall_for_llm": {},
            "allowed_commands": self.mock_config.agent.allowed_commands,
            "telegram_config": None,
        }

        # 模拟LLM实例，确保get_name方法返回正确的名称
        mock_llm = MagicMock()
        mock_llm.get_name.return_value = "test_llm"

        # 模拟agent和lifecycle
        mock_agent = MagicMock()
        mock_lifecycle = MagicMock()
        mock_agent.lifecycle = mock_lifecycle

        # 使用patch模拟所有必要依赖，注意Agent是从linhai.agent.main导入到create模块的
        # 我们使用side_effect来确保调用Agent()时返回我们准备好的mock_agent
        def mock_agent_side_effect(*args, **kwargs):
            return mock_agent

        with (
            patch("linhai.agent.create.Agent", side_effect=mock_agent_side_effect),
            patch("linhai.agent.create._create_llm_instances", return_value=[mock_llm]),
            patch(
                "linhai.agent.create._create_tool_manager",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch("linhai.agent.create._create_pinned_messages", return_value=[]),
            patch("linhai.agent.create.initialize_secret_system"),
            patch("linhai.agent.lifecycle.Lifecycle", return_value=mock_lifecycle),
            patch(
                "linhai.plugin.planning.PlanningStatusReminderPlugin"
            ) as mock_planning_plugin_cls,
            patch(
                "linhai.plugin.planning.UserInputRuntimeMessagePlugin"
            ) as mock_user_input_plugin_cls,
        ):

            # 设置插件实例
            mock_planning_status_plugin_instance = MagicMock()
            mock_user_input_plugin_instance = MagicMock()
            mock_planning_plugin_cls.return_value = mock_planning_status_plugin_instance
            mock_user_input_plugin_cls.return_value = mock_user_input_plugin_instance

            # 执行函数
            await create_agent_from_config(context=context)

            # 验证planning插件被实例化和注册
            from linhai.plugin.planning import (
                PlanningStatusReminderPlugin,
                UserInputRuntimeMessagePlugin,
            )

            mock_planning_plugin_cls.assert_called_once_with(self.mock_registry)
            mock_user_input_plugin_cls.assert_called_once_with(self.mock_registry)

            # 验证register被调用，且参数不为空
            mock_planning_status_plugin_instance.register.assert_called_once()
            mock_user_input_plugin_instance.register.assert_called_once()

            # 检查register调用参数是否非空
            planning_call_args = mock_planning_status_plugin_instance.register.call_args
            user_input_call_args = mock_user_input_plugin_instance.register.call_args
            self.assertIsNotNone(planning_call_args[0][0])
            self.assertIsNotNone(user_input_call_args[0][0])

    async def test_plugin_registration_with_planning_false(self):
        # 测试planning为False时插件不被注册
        from linhai.agent.create import create_agent_from_config

        # 创建上下文配置，planning为False
        context = {
            "planning": False,
            "registry": self.mock_registry,
            "cli_args": self.mock_cli_args,
            "config": self.mock_config,
            "config_basedir": self.mock_config_basedir,
            "llms": self.mock_config.llm,
            "checklist_path": None,
            "user_prompt": None,
            "llm_name": "test_llm",
            "max_toolcall_token_in_round": 30000,
            "toolsets_config": self.mock_config.tools.toolsets,
            "override_toolsets": self.mock_config.agent.override_toolsets,
            "compress_threshold": self.mock_config.agent.compress_threshold,
            "enable_directory_change_detection": self.mock_config.agent.enable_directory_change_detection,
            "max_toolcall_for_llm": {},
            "allowed_commands": self.mock_config.agent.allowed_commands,
            "telegram_config": None,
        }

        # 创建模拟的Lifecycle对象
        mock_lifecycle = MagicMock()

        # 模拟agent
        mock_agent = MagicMock()
        mock_agent.lifecycle = mock_lifecycle

        # 模拟LLM实例，确保get_name方法返回正确的名称
        mock_llm = MagicMock()
        mock_llm.get_name.return_value = "test_llm"

        # 模拟planning插件
        mock_planning_status_plugin_instance = MagicMock()
        mock_user_input_plugin_instance = MagicMock()

        # 使用patch模拟所有必要依赖，注意Agent是从linhai.agent.main导入到create模块的
        with (
            patch("linhai.agent.create.Agent", return_value=mock_agent),
            patch("linhai.agent.create._create_llm_instances", return_value=[mock_llm]),
            patch(
                "linhai.agent.create._create_tool_manager",
                return_value=(MagicMock(), MagicMock()),
            ),
            patch("linhai.agent.create._create_pinned_messages", return_value=[]),
            patch("linhai.agent.create.initialize_secret_system"),
            patch(
                "linhai.plugin.planning.PlanningStatusReminderPlugin",
                return_value=mock_planning_status_plugin_instance,
            ),
            patch(
                "linhai.plugin.planning.UserInputRuntimeMessagePlugin",
                return_value=mock_user_input_plugin_instance,
            ),
        ):

            # 执行函数
            await create_agent_from_config(context=context)

            # 验证planning插件没有被实例化或注册
            from linhai.plugin.planning import (
                PlanningStatusReminderPlugin,
                UserInputRuntimeMessagePlugin,
            )

            PlanningStatusReminderPlugin.assert_not_called()
            UserInputRuntimeMessagePlugin.assert_not_called()
            mock_planning_status_plugin_instance.register.assert_not_called()
            mock_user_input_plugin_instance.register.assert_not_called()


if __name__ == "__main__":
    unittest.main()
