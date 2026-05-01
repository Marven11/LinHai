import asyncio
import base64
import unittest
from unittest.mock import AsyncMock, Mock

from linhai.tool.base import (
    SuccessfulToolResult,
    FailedToolResult,
    FileContentToolResult,
)
from linhai.machine_control.bash_host.bash_host import BashHostControl
from linhai.machine_control.bash_host.file import (
    MAX_FILE_SIZE,
    read_file,
    write_file,
    replace_file_content,
    list_files,
    get_absolute_path,
    read_file_with_sed,
)
from linhai.registry import Registry
from linhai.tool.base import SuccessfulToolResult, FailedToolResult


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _make_host() -> BashHostControl:
    registry = Mock(spec=Registry)
    registry.send_if_exists = AsyncMock()
    host = BashHostControl(registry=registry)
    host._tmp_dir = "/tmp/linhai_test"
    host.execute_raw = AsyncMock()
    return host


class TestReadFile(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_file_not_exist(self):
        async def test():
            host = _make_host()
            host.execute_raw.return_value = (1, "", "")
            result = await read_file(host, "/no/such/file")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("不存在", result.content)

        self.loop.run_until_complete(test())

    def test_file_too_large(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(MAX_FILE_SIZE + 1), ""),
            ]
            result = await read_file(host, "/big/file")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("过大", result.content)

        self.loop.run_until_complete(test())

    def test_read_success(self):
        async def test():
            content = "hello world"
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(len(content.encode())), ""),
                (0, _b64(content), ""),
            ]
            result = await read_file(host, "/some/file")
            self.assertIsInstance(result, FileContentToolResult)
            self.assertEqual(result.content, content)

        self.loop.run_until_complete(test())


class TestWriteFile(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_dir_not_writable(self):
        async def test():
            host = _make_host()
            host.execute_raw.return_value = (1, "", "")
            result = await write_file(host, "/no/write/dir/file.txt", "data")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("不可写", result.content)

        self.loop.run_until_complete(test())

    def test_file_exists_no_override(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
            ]
            result = await write_file(host, "/existing/file", "data", override=False)
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("已存在", result.content)

        self.loop.run_until_complete(test())

    def test_write_success(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (1, "", ""),
                (0, "", ""),
            ]
            result = await write_file(host, "/new/file", "hello")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("成功", result.content)

        self.loop.run_until_complete(test())

    def test_write_override(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
            ]
            result = await write_file(host, "/existing/file", "new data", override=True)
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("成功", result.content)

        self.loop.run_until_complete(test())


class TestReplaceFileContent(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_old_not_found(self):
        async def test():
            host = _make_host()
            content = "hello world"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(len(content.encode())), ""),
                (0, "12345 11", ""),
                (0, _b64(content), ""),
            ]
            result = await replace_file_content(host, "/file", "xyz", "abc")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("未找到", result.content)

        self.loop.run_until_complete(test())

    def test_replace_single_match(self):
        async def test():
            host = _make_host()
            content = "hello world"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(len(content.encode())), ""),
                (0, "99999 11", ""),
                (0, _b64(content), ""),
                (0, "", ""),
                (0, "OK", ""),
                (0, "", ""),
            ]
            result = await replace_file_content(host, "/file", "world", "earth")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("替换次数: 1", result.content)

        self.loop.run_until_complete(test())

    def test_replace_multiple_match_no_times(self):
        async def test():
            host = _make_host()
            content = "aaa aaa aaa"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(len(content.encode())), ""),
                (0, "99999 11", ""),
                (0, _b64(content), ""),
            ]
            result = await replace_file_content(host, "/file", "aaa", "bbb")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("多次匹配", result.content)

        self.loop.run_until_complete(test())

    def test_replace_all(self):
        async def test():
            host = _make_host()
            content = "aaa bbb aaa"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(len(content.encode())), ""),
                (0, "99999 11", ""),
                (0, _b64(content), ""),
                (0, "", ""),
                (0, "OK", ""),
                (0, "", ""),
            ]
            result = await replace_file_content(host, "/file", "aaa", "ccc", -1)
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("替换次数: 2", result.content)

        self.loop.run_until_complete(test())

    def test_replace_file_changed(self):
        async def test():
            host = _make_host()
            content = "hello world"
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, str(len(content.encode())), ""),
                (0, "99999 11", ""),
                (0, _b64(content), ""),
                (0, "", ""),
                (0, "CHANGED", ""),
                (0, "", ""),
            ]
            result = await replace_file_content(host, "/file", "world", "earth")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("被外部修改", result.content)

        self.loop.run_until_complete(test())


class TestListFiles(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_dir_not_exist(self):
        async def test():
            host = _make_host()
            host.execute_raw.return_value = (1, "", "")
            result = await list_files(host, "/no/dir")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("不存在", result.content)

        self.loop.run_until_complete(test())

    def test_list_success(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "total 4\nfile.txt", ""),
            ]
            result = await list_files(host, "/some/dir")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("file.txt", result.content)

        self.loop.run_until_complete(test())


class TestGetAbsolutePath(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_success(self):
        async def test():
            host = _make_host()
            host.execute_raw.return_value = (0, "/home/user/file.txt", "")
            result = await get_absolute_path(host, "file.txt")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("/home/user/file.txt", result.content)

        self.loop.run_until_complete(test())

    def test_failure(self):
        async def test():
            host = _make_host()
            host.execute_raw.return_value = (1, "", "error")
            result = await get_absolute_path(host, "bad/path")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("失败", result.content)

        self.loop.run_until_complete(test())


class TestReadFileWithSed(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_sed_substitution_rejected(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, "replaced", ""),
            ]
            result = await read_file_with_sed(host, "s/old/new/", "/file")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("不能修改", result.content)

        self.loop.run_until_complete(test())

    def test_sed_success(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (0, "line1\nline2", ""),
            ]
            result = await read_file_with_sed(host, "1,2p", "/file")
            self.assertIsInstance(result, SuccessfulToolResult)
            self.assertIn("line1", result.content)

        self.loop.run_until_complete(test())

    def test_sed_failure(self):
        async def test():
            host = _make_host()
            host.execute_raw.side_effect = [
                (0, "", ""),
                (0, "", ""),
                (0, "", ""),
                (1, "", "sed error"),
            ]
            result = await read_file_with_sed(host, "bad_expr", "/file")
            self.assertIsInstance(result, FailedToolResult)
            self.assertIn("sed执行失败", result.content)

        self.loop.run_until_complete(test())


if __name__ == "__main__":
    unittest.main()
