"""测试agent_plugin模块。"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from linhai.agent_plugin import TaskPlanningPlugin, BadMultiToolCall, ChineseEndOfSentencePlugin


class TestTaskPlanningPlugin(unittest.IsolatedAsyncioTestCase):
    """测试TaskPlanningPlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.plugin = TaskPlanningPlugin()
        self.agent = MagicMock()
        self.answer = MagicMock()
        self.answer.get_reasoning_message = MagicMock(return_value=None)
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_task_planning(self):
        """测试有任务规划标记的情况。"""
        full_response = """当前任务规划

- [ ] 任务1
- [x] 任务2
- [ ] 任务3"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        # 有任务规划标记，不应该添加警告消息
        self.assertEqual(len(self.agent.messages), 0)

    async def test_after_message_generation_without_task_planning(self):
        """测试没有任务规划标记的情况。"""
        full_response = """当前任务

任务1
任务2
任务3"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        # 没有任务规划标记，应该添加警告消息
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("你没有输出任务规划", self.agent.messages[0].message)

    async def test_after_message_generation_with_long_content(self):
        """测试长内容中的任务规划检查。"""
        # 创建一个长内容，确保超过8000字符
        long_content = "任务描述" + "x" * 8000

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, long_content, self.tool_calls
        )

        # 长内容中没有任务规划标记，应该添加警告消息
        self.assertEqual(len(self.agent.messages), 1)


if __name__ == "__main__":
    unittest.main()


class TestBadMultiToolCall(unittest.IsolatedAsyncioTestCase):
    """测试BadMultiToolCall类。"""

    def setUp(self):
        """设置测试环境。"""
        self.plugin = BadMultiToolCall()
        self.agent = MagicMock()
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_after_message_generation.assert_called_once_with(
            self.plugin.after_message_generation
        )

    async def test_after_message_generation_with_bad_multi_tool_call(self):
        """测试有多个工具调用但没有输出原因的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        # 有多个工具调用但没有原因，应该添加警告消息
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("忘记在多个工具调用之间输出可以同时调用的原因", self.agent.messages[0].message)

    async def test_after_message_generation_with_good_multi_tool_call(self):
        """测试有正常分隔的工具调用块的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.agent.messages), 0)

    async def test_after_message_generation_with_single_tool_call(self):
        """测试只有单个工具调用的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        # 只有一个工具调用，不应该添加警告消息
        self.assertEqual(len(self.agent.messages), 0)

    async def test_after_message_generation_with_reason_output_after_no_reason(self):
        """测试上一条消息没有输出原因，当前消息输出了原因的情况。"""
        # 第一条消息：没有输出原因
        full_response1 = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response1, self.tool_calls
        )

        # 第一条消息没有原因，不应该有提醒
        self.assertEqual(len(self.agent.messages), 0)

        # 第二条消息：输出了原因
        full_response2 = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response2, self.tool_calls
        )

        self.assertEqual(len(self.agent.messages), 0)

    async def test_after_message_generation_with_reason_output_after_reason(self):
        """测试上一条消息输出了原因，当前消息也输出了原因的情况。"""
        # 重置插件状态
        self.plugin.last_message_had_reason = True
        
        # 第一条消息：输出了原因
        full_response1 = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response1, self.tool_calls
        )

        # 第一条消息有原因，且上一条也有原因，不应该有提醒
        self.assertEqual(len(self.agent.messages), 0)
    async def test_after_message_generation_with_multiple_tool_calls_no_reason(self):
        """测试有多个工具调用但没有输出原因的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        # 有多个工具调用但没有原因，应该添加警告消息
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("忘记在多个工具调用之间输出可以同时调用的原因", self.agent.messages[0].message)

    async def test_after_message_generation_with_multiple_tool_calls_and_reason(self):
        """测试有多个工具调用且输出了原因的情况。"""
        full_response = """一些内容

```json toolcall
{"name": "tool1", "arguments": {}}
```

同时调用的原因：这两个工具没有顺序依赖

```json toolcall
{"name": "tool2", "arguments": {}}
```

更多内容"""

        self.agent.messages = []

        await self.plugin.after_message_generation(
            self.agent, self.answer, full_response, self.tool_calls
        )

        self.assertEqual(len(self.agent.messages), 0)


class TestChineseEndOfSentencePlugin(unittest.IsolatedAsyncioTestCase):
    """测试ChineseEndOfSentencePlugin类。"""

    def setUp(self):
        """设置测试环境。"""
        self.plugin = ChineseEndOfSentencePlugin()
        self.agent = MagicMock()
        self.answer = MagicMock()
        self.tool_calls = []

    def test_register(self):
        """测试插件注册。"""
        lifecycle = MagicMock()
        self.plugin.register(lifecycle)
        lifecycle.register_during_message_generation.assert_called_once_with(
            self.plugin.during_message_generation
        )

    async def test_during_message_generation_with_chinese_end_marker(self):
        """测试有中文句子结束标记的情况。"""
        current_content = """这是一些内容
这是一行中文<｜end▁of▁thought｜><｜end▁of▁sentence｜>
这是另一行内容"""

        self.agent.messages = []
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        # 应该检测到中文句子结束标记并打断输出
        self.assertTrue(result)
        self.answer.interrupt.assert_called_once()
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("检测到中文句子结束标记", self.agent.messages[0].message)

    async def test_during_message_generation_without_chinese_end_marker(self):
        """测试没有中文句子结束标记的情况。"""
        current_content = """这是一些内容
这是一行中文<｜end▁of▁sentence｜>
这是另一行内容"""

        self.agent.messages = []
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()


        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        self.assertTrue(result)

    async def test_during_message_generation_with_non_chinese_before_marker(self):
        """测试标记前面有非汉字的情况。"""
        current_content = """这是一些内容
这是一行中文abc<｜end▁of▁sentence｜>
这是另一行内容"""

        self.agent.messages = []
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        # 标记前面有非汉字，不应该打断输出
        self.assertFalse(result)
        self.assertEqual(len(self.agent.messages), 0)

    async def test_during_message_generation_with_different_markers(self):
        """测试不同的结束标记。"""
        current_content = """这是一些内容
这是一行中文<｜end▁of▁thought｜>
这是另一行内容"""

        self.agent.messages = []
        self.agent.group_chat = MagicMock()
        self.agent.group_chat.send = AsyncMock()

        result = await self.plugin.during_message_generation(
            self.agent, self.answer, current_content
        )

        # 应该检测到中文句子结束标记并打断输出
        self.assertTrue(result)
        self.answer.interrupt.assert_called_once()
        self.assertEqual(len(self.agent.messages), 1)
        self.assertIn("检测到中文句子结束标记", self.agent.messages[0].message)