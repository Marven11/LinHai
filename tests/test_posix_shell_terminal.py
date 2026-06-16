"""SSH终端工具测试模块，使用Fake对象驱动测试PosixShellControl终端行为"""

import asyncio
import base64
import json
import unittest
from unittest.mock import Mock

from linhai.machine_control.posix_shell.posix_shell_control import PosixShellControl
from linhai.registry import Registry
from linhai.tool.base import SuccessfulToolResult, FailedToolResult
from linhai.machine_control.http_message import HttpToolResult


class _FakeTransport:
    """Fake TrojanTransport用于终端生命周期测试"""

    def __init__(self):
        self.terminals: dict[str, list[str]] = {}
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(
        self, name: str, args: dict
    ) -> SuccessfulToolResult | FailedToolResult:
        self.calls.append((name, args))
        if name == "terminal_create":
            term_id = f"term_{len(self.terminals)}"
            self.terminals[term_id] = []
            return SuccessfulToolResult(content=term_id)
        if name == "terminal_send_string":
            tid = args.get("term_id", "unknown")
            if tid not in self.terminals:
                return FailedToolResult(content="终端不存在: " + tid)
            self.terminals[tid].append(args.get("string", ""))
            return SuccessfulToolResult(
                content="已发送字符串: " + args.get("string", "")
            )
        if name == "terminal_send_keys":
            tid = args.get("term_id", "unknown")
            if tid not in self.terminals:
                return FailedToolResult(content="终端不存在: " + tid)
            return SuccessfulToolResult(
                content="已发送按键: " + str(args.get("keys", []))
            )
        if name == "terminal_read_screen":
            tid = args.get("term_id", "unknown")
            if tid not in self.terminals:
                return FailedToolResult(content="终端不存在: " + tid)
            history = "\n".join(self.terminals[tid])
            raw = history.encode("utf-8") if history else b"$ "
            encoded = base64.b64encode(raw).decode("utf-8")
            return SuccessfulToolResult(content=encoded)
        if name == "terminal_close":
            tid = args.get("term_id", "unknown")
            if tid not in self.terminals:
                return FailedToolResult(content="终端不存在: " + tid)
            del self.terminals[tid]
            return SuccessfulToolResult(content="已关闭终端 " + tid)
        return FailedToolResult(content="unknown tool: " + name)


class TestSshTerminalLifecycle(unittest.IsolatedAsyncioTestCase):
    """使用FakeTransport测试SSH终端完整生命周期"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def _make_control(self) -> tuple[PosixShellControl, _FakeTransport]:
        registry = Mock(spec=Registry)
        ctrl = PosixShellControl(registry=registry)
        transport = _FakeTransport()
        ctrl.call_tool = transport.call_tool
        return ctrl, transport

    async def _test_terminal_lifecycle(self):
        ctrl, transport = self._make_control()

        create_result = await ctrl.terminal_create(columns=100, lines=30)
        self.assertIsInstance(create_result, SuccessfulToolResult)
        term_id = create_result.content
        self.assertIn("term_", term_id)

        send_result = await ctrl.terminal_send_string(
            terminal_id=term_id, string="echo hello", with_enter=True
        )
        self.assertIn("已发送字符串", send_result.content)

        send_result2 = await ctrl.terminal_send_string(
            terminal_id=term_id, string="ls -la", with_enter=False
        )
        self.assertIn("已发送字符串", send_result2.content)

        read_result = await ctrl.terminal_read_screen(terminal_id=term_id)
        self.assertIsInstance(read_result, SuccessfulToolResult)

        close_result = await ctrl.terminal_close(terminal_id=term_id)
        self.assertIn("已关闭终端", close_result.content)

        self.assertEqual(len(transport.calls), 5)

    def test_terminal_lifecycle(self):
        self.loop.run_until_complete(self._test_terminal_lifecycle())

    async def _test_nonexistent_terminal_operations(self):
        ctrl, transport = self._make_control()

        read_result = await ctrl.terminal_read_screen(terminal_id="nonexistent")
        self.assertIsInstance(read_result, FailedToolResult)
        self.assertIn("终端不存在", read_result.content)

        close_result = await ctrl.terminal_close(terminal_id="nonexistent")
        self.assertIsInstance(close_result, FailedToolResult)
        self.assertIn("终端不存在", close_result.content)

        send_result = await ctrl.terminal_send_string(
            terminal_id="nonexistent", string="test", with_enter=True
        )
        self.assertIsInstance(send_result, FailedToolResult)
        self.assertIn("终端不存在", send_result.content)

    def test_nonexistent_terminal_operations(self):
        self.loop.run_until_complete(self._test_nonexistent_terminal_operations())

    async def _test_multiple_terminals_independent(self):
        ctrl, transport = self._make_control()

        t1 = (await ctrl.terminal_create()).content
        t2 = (await ctrl.terminal_create()).content
        self.assertNotEqual(t1, t2)

        await ctrl.terminal_send_string(
            terminal_id=t1, string="from t1", with_enter=True
        )
        await ctrl.terminal_send_string(
            terminal_id=t2, string="from t2", with_enter=True
        )

        await ctrl.terminal_close(terminal_id=t1)
        self.assertEqual(len(transport.terminals), 1)
        self.assertNotIn(t1, transport.terminals)
        self.assertIn(t2, transport.terminals)

    def test_multiple_terminals_independent(self):
        self.loop.run_until_complete(self._test_multiple_terminals_independent())

    async def _test_send_keys(self):
        ctrl, transport = self._make_control()

        term_id = (await ctrl.terminal_create()).content
        result = await ctrl.terminal_send_keys(terminal_id=term_id, keys=["ctrl+c"])
        self.assertIn("已发送按键", result.content)
        self.assertIn("ctrl+c", result.content)

    def test_send_keys(self):
        self.loop.run_until_complete(self._test_send_keys())


class TestSshHttpRequest(unittest.IsolatedAsyncioTestCase):
    """测试SSH机器http_request代理行为"""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    async def _test_http_request_delegation(self):
        registry = Mock(spec=Registry)
        ctrl = PosixShellControl(registry=registry)

        async def fake_call_tool(name: str, args: dict):
            if name == "http_request":
                return SuccessfulToolResult(
                    content=json.dumps(
                        {
                            "status_code": 200,
                            "headers": {"content-type": "text/html"},
                            "content_base64": base64.b64encode(
                                b"response body"
                            ).decode(),
                            "content_type": "text/html",
                        }
                    )
                )
            return FailedToolResult(content="unknown")

        ctrl.call_tool = fake_call_tool

        result = await ctrl.http_request(method="GET", url="http://example.com")
        self.assertIsInstance(result, HttpToolResult)
        self.assertEqual(result.status_code, 200)

    def test_http_request_delegation(self):
        self.loop.run_until_complete(self._test_http_request_delegation())


if __name__ == "__main__":
    unittest.main()
