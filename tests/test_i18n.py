import unittest
from unittest.mock import patch, Mock

from linhai.utils.i18n import t


class TestI18n(unittest.TestCase):
    def test_missing_en_raises_value_error(self):
        with self.assertRaises(ValueError):
            t({"zh_CN": "测试"})

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_match_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"zh_CN": "平均长度: xxx token", "en": "Average length: xxx token"})
        self.assertEqual(result, "平均长度: xxx token")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_fallback_to_en_for_unknown_locale(self, mock_getlocale):
        mock_getlocale.return_value = ("ja_JP", "UTF-8")
        result = t({"zh_CN": "测试", "en": "test"})
        self.assertEqual(result, "test")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_none_locale_returns_en(self, mock_getlocale):
        mock_getlocale.return_value = (None, None)
        result = t({"zh_CN": "测试", "en": "test"})
        self.assertEqual(result, "test")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_only_en_key(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"en": "test"})
        self.assertEqual(result, "test")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_en_us_falls_to_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t({"zh_CN": "测试", "en": "test"})
        self.assertEqual(result, "test")

    def test_t_function_in_app_py_context(self):
        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("zh_CN", "UTF-8")
            result = t(
                {
                    "zh_CN": "Enter发送，Shift+Enter换行（如果终端支持）",
                    "en": "Enter to send, Shift+Enter for newline (if terminal supports)",
                }
            )
            self.assertEqual(result, "Enter发送，Shift+Enter换行（如果终端支持）")

        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("en_US", "UTF-8")
            result = t(
                {
                    "zh_CN": "Enter发送，Shift+Enter换行（如果终端支持）",
                    "en": "Enter to send, Shift+Enter for newline (if terminal supports)",
                }
            )
            self.assertEqual(
                result, "Enter to send, Shift+Enter for newline (if terminal supports)"
            )

    def test_suicide_tool_descriptions(self):
        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("zh_CN", "UTF-8")
            result = t(
                {"zh_CN": "杀死自己并退出APP", "en": "Kill self and exit the app"}
            )
            self.assertEqual(result, "杀死自己并退出APP")

        with patch("linhai.utils.i18n.locale.getlocale") as mock_getlocale:
            mock_getlocale.return_value = ("en_US", "UTF-8")
            result = t(
                {
                    "zh_CN": "退出代码，0表示成功，非0表示错误",
                    "en": "Exit code, 0 for success, non-zero for error",
                }
            )
            self.assertEqual(result, "Exit code, 0 for success, non-zero for error")

    def test_app_py_imports_work(self):
        from linhai.tui.app import TUIApp
        from linhai.utils.i18n import t


class TestComponentsI18n(unittest.TestCase):
    @patch("linhai.utils.i18n.locale.getlocale")
    def test_tool_collapse_header_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"zh_CN": "▼ 工具", "en": "▼ Tool"})
        self.assertEqual(result, "▼ 工具")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_tool_collapse_header_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t({"zh_CN": "▼ 工具", "en": "▼ Tool"})
        self.assertEqual(result, "▼ Tool")

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_tool_call_expand_collapse(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        self.assertEqual(
            t({"zh_CN": "tool call [点击展开]", "en": "tool call [click to expand]"}),
            "tool call [点击展开]",
        )
        mock_getlocale.return_value = ("en_US", "UTF-8")
        self.assertEqual(
            t({"zh_CN": "tool call [点击展开]", "en": "tool call [click to expand]"}),
            "tool call [click to expand]",
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_tool_call_hide_toggle(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        self.assertEqual(
            t({"zh_CN": "tool call [点击隐藏]", "en": "tool call [click to hide]"}),
            "tool call [点击隐藏]",
        )
        mock_getlocale.return_value = ("en_US", "UTF-8")
        self.assertEqual(
            t({"zh_CN": "tool call [点击隐藏]", "en": "tool call [click to hide]"}),
            "tool call [click to hide]",
        )

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_reasoning_toggle(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        self.assertEqual(
            t({"zh_CN": "[点击隐藏]", "en": "[click to hide]"}), "[点击隐藏]"
        )
        self.assertEqual(
            t({"zh_CN": "[点击展开]", "en": "[click to expand]"}), "[点击展开]"
        )
        mock_getlocale.return_value = ("en_US", "UTF-8")
        self.assertEqual(
            t({"zh_CN": "[点击隐藏]", "en": "[click to hide]"}), "[click to hide]"
        )
        self.assertEqual(
            t({"zh_CN": "[点击展开]", "en": "[click to expand]"}),
            "[click to expand]",
        )

    def test_components_import(self):
        from linhai.tui.components import (
            _ToolCallCollapseHeader,
            ToolCallWidget,
            ReasoningContentWidget,
        )


class TestPromptI18n(unittest.TestCase):
    def test_all_prompt_constants_are_strings(self):
        from linhai import prompt

        constants = [
            prompt.OVERVIEW,
            prompt.REASONING_EFFORT_MAX,
            prompt.INTRODUCTION_TOOL_USE,
            prompt.INTRODUCTION_WAITING_USER,
            prompt.INTRODUCTION_GLOBAL_PROMPT,
            prompt.INTRODUCTION_CONTEXT_MANAGEMENT,
            prompt.INTRODUCTION_SECRET_SYSTEM,
            prompt.INTRODUCTION_MACHINE_CONTROL_BASIC,
            prompt.INTRODUCTION_MACHINE_CONTROL,
            prompt.INTRODUCTION_PLANNING_MODE,
            prompt.RULES_TOOL_USE,
            prompt.RULES_CODING_STYLE,
            prompt.RULES_USER_ITERATION,
            prompt.EXAMPLES_TOOL_CALL,
            prompt.EXAMPLES_SECRET_USAGE,
            prompt.EXAMPLE_MULTIHOP_MACHINES,
            prompt.EXAMPLES_PLANNING_MODE,
            prompt.AGENTS_MD,
            prompt.BOOTSTRAP_MD,
            prompt.IDENTITY_MD,
            prompt.SOUL_MD,
            prompt.USER_MD,
            prompt.REMINDER_MD,
            prompt.COMPRESS_RANGE_PROMPT,
            prompt.PLANNING_MODE_PROMPT,
        ]
        for const in constants:
            self.assertIsInstance(const, str)
            self.assertTrue(len(const) > 0)

    def test_format_placeholders_in_secret_system(self):
        from linhai.prompt import INTRODUCTION_SECRET_SYSTEM

        self.assertIn("{secrets_list}", INTRODUCTION_SECRET_SYSTEM)

    def test_format_placeholders_in_planning_mode(self):
        from linhai.prompt import INTRODUCTION_PLANNING_MODE

        self.assertIn("{status_file}", INTRODUCTION_PLANNING_MODE)
        self.assertIn("{todolist_file}", INTRODUCTION_PLANNING_MODE)
        self.assertIn("{design_file}", INTRODUCTION_PLANNING_MODE)

    def test_format_placeholders_in_planning_mode_prompt(self):
        from linhai.prompt import PLANNING_MODE_PROMPT

        self.assertIn("{status_file}", PLANNING_MODE_PROMPT)
        self.assertIn("{todolist_file}", PLANNING_MODE_PROMPT)
        self.assertIn("{design_file}", PLANNING_MODE_PROMPT)

    def test_format_placeholders_in_compress_range(self):
        from linhai.prompt import COMPRESS_RANGE_PROMPT

        self.assertIn("{|SUMMERIZATION|}", COMPRESS_RANGE_PROMPT)
        self.assertIn("{|SUGGESTED_MESSAGE_COUNT|}", COMPRESS_RANGE_PROMPT)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_prompt_overview_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t({"zh_CN": "你是林海漫游", "en": "You are LinHai Wanderer"})
        self.assertIn("林海漫游", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_prompt_overview_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t({"zh_CN": "你是林海漫游", "en": "You are LinHai Wanderer"})
        self.assertIn("LinHai Wanderer", result)


class TestNotificationMessageI18n(unittest.TestCase):
    @patch("linhai.utils.i18n.locale.getlocale")
    def test_planning_status_reminder_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "你已经连续5次没有修改STATUS.md，你偏离计划了吗？",
                "en": "You have not modified STATUS.md for 5 consecutive times. Have you deviated from the plan?",
            }
        )
        self.assertIn("STATUS.md", result)
        self.assertIn("偏离计划", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_planning_status_reminder_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "你已经连续5次没有修改STATUS.md，你偏离计划了吗？",
                "en": "You have not modified STATUS.md for 5 consecutive times. Have you deviated from the plan?",
            }
        )
        self.assertIn("STATUS.md", result)
        self.assertIn("deviated", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_planning_todolist_reminder_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "你已经连续8次没有修改TODOLIST.md，你偏离任务了吗？",
                "en": "You have not modified TODOLIST.md for 8 consecutive times. Have you deviated from the task?",
            }
        )
        self.assertIn("TODOLIST.md", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_planning_todolist_reminder_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "你已经连续8次没有修改TODOLIST.md，你偏离任务了吗？",
                "en": "You have not modified TODOLIST.md for 8 consecutive times. Have you deviated from the task?",
            }
        )
        self.assertIn("TODOLIST.md", result)
        self.assertIn("deviated", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_orchestration_red_light_suggestion_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "建议: 立即暂停当前任务，开始使用context_forget_large_message清理上下文",
                "en": "Suggestion: Stop current task immediately and start using context_forget_large_message to clean up context",
            }
        )
        self.assertIn("context_forget_large_message", result)
        self.assertIn("建议", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_orchestration_red_light_suggestion_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "建议: 立即暂停当前任务，开始使用context_forget_large_message清理上下文",
                "en": "Suggestion: Stop current task immediately and start using context_forget_large_message to clean up context",
            }
        )
        self.assertIn("context_forget_large_message", result)
        self.assertIn("Suggestion", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_orchestration_green_light_suggestion_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "建议: 不要担心消息限制，立即工作",
                "en": "Suggestion: Do not worry about message limits, keep working",
            }
        )
        self.assertIn("立即工作", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_orchestration_green_light_suggestion_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "建议: 不要担心消息限制，立即工作",
                "en": "Suggestion: Do not worry about message limits, keep working",
            }
        )
        self.assertIn("keep working", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_tool_call_managers_model_limit_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "你现在是test-model，为了避免一次性造成大量错误，runtime会在你调用超过5个工具时打断你",
                "en": "You are now test-model, runtime will interrupt after 5 tool calls to prevent mass errors",
            }
        )
        self.assertIn("test-model", result)
        self.assertIn("打断", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_tool_call_managers_model_limit_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "你现在是test-model，为了避免一次性造成大量错误，runtime会在你调用超过5个工具时打断你",
                "en": "You are now test-model, runtime will interrupt after 5 tool calls to prevent mass errors",
            }
        )
        self.assertIn("test-model", result)
        self.assertIn("interrupt", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_message_checkers_only_reasoning_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "检测到在思考后没有输出任何内容而是在</thinking>标签前就输出了工具调用等，应该在</thinking>标签后输出实际内容",
                "en": "Detected no output after thinking, with tool calls before </thinking> tag. Actual content should be output after the </thinking> tag",
            }
        )
        self.assertIn("</thinking>", result)
        self.assertIn("检测", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_message_checkers_only_reasoning_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "检测到在思考后没有输出任何内容而是在</thinking>标签前就输出了工具调用等，应该在</thinking>标签后输出实际内容",
                "en": "Detected no output after thinking, with tool calls before </thinking> tag. Actual content should be output after the </thinking> tag",
            }
        )
        self.assertIn("</thinking>", result)
        self.assertIn("Detected", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_machine_control_current_machine_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "当前在master_host上",
                "en": "Currently on master_host",
            }
        )
        self.assertIn("master_host", result)
        self.assertIn("当前在", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_machine_control_current_machine_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "当前在master_host上",
                "en": "Currently on master_host",
            }
        )
        self.assertIn("master_host", result)
        self.assertIn("Currently", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_security_config_allowed_commands_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "允许的命令: ls, cat",
                "en": "Allowed commands: ls, cat",
            }
        )
        self.assertIn("允许的命令", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_security_config_allowed_commands_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "允许的命令: ls, cat",
                "en": "Allowed commands: ls, cat",
            }
        )
        self.assertIn("Allowed commands", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_planning_design_reminder_zh_cn(self, mock_getlocale):
        mock_getlocale.return_value = ("zh_CN", "UTF-8")
        result = t(
            {
                "zh_CN": "当前没有查看DESIGN.md的内容，你应该重新读取再继续任务吗？"
                "你应该如何修改DESIGN.md以符合任务的最新要求？",
                "en": "DESIGN.md content is not currently visible. Should you re-read it before continuing? "
                "How should you modify DESIGN.md to meet the latest task requirements?",
            }
        )
        self.assertIn("DESIGN.md", result)
        self.assertIn("重新读取", result)

    @patch("linhai.utils.i18n.locale.getlocale")
    def test_planning_design_reminder_en(self, mock_getlocale):
        mock_getlocale.return_value = ("en_US", "UTF-8")
        result = t(
            {
                "zh_CN": "当前没有查看DESIGN.md的内容，你应该重新读取再继续任务吗？"
                "你应该如何修改DESIGN.md以符合任务的最新要求？",
                "en": "DESIGN.md content is not currently visible. Should you re-read it before continuing? "
                "How should you modify DESIGN.md to meet the latest task requirements?",
            }
        )
        self.assertIn("DESIGN.md", result)
        self.assertIn("re-read", result)


if __name__ == "__main__":
    unittest.main()
