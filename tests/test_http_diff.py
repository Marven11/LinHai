import os
import tempfile
import unittest
from pathlib import Path

from linhai.machine_control.http_message import (
    HttpToolResult,
    HttpTextDiffToolResult,
)
from linhai.utils.http_diff import http_diff


class TestHttpDiff(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.file1 = os.path.join(self.tmpdir, "file1.txt")
        self.file2 = os.path.join(self.tmpdir, "file2.txt")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir)

    def test_identical_files_empty_diff(self):
        Path(self.file1).write_text("hello world")
        Path(self.file2).write_text("hello world")
        result = http_diff(self.file1, self.file2)
        self.assertEqual(result, "")

    def test_different_lines(self):
        Path(self.file1).write_text("line1\nline2\nline3")
        Path(self.file2).write_text("line1\nline2_changed\nline3")
        result = http_diff(self.file1, self.file2)
        self.assertIn("- line2", result)
        self.assertIn("+ line2", result)

    def test_absolute_path_required(self):
        with self.assertRaises(ValueError):
            http_diff("relative/path.txt", "/absolute/path.txt")
        with self.assertRaises(ValueError):
            http_diff("/absolute/path.txt", "relative/path.txt")

    def test_long_line_split_80(self):
        line = "A" * 150
        Path(self.file1).write_text(line)
        Path(self.file2).write_text("B" * 150)
        result = http_diff(self.file1, self.file2)
        lines = result.split("\n")
        self.assertTrue(len(lines) >= 2)

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            http_diff("/nonexistent/file1.txt", "/nonexistent/file2.txt")


class TestHttpTextDiffToolResult(unittest.TestCase):
    def test_create_valid(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={"content-type": "text/plain"},
            is_binary=False,
            size=10,
            body="test body",
        )
        result = HttpTextDiffToolResult(
            http_result=http_result,
            fromfile="/tmp/old.html",
            tofile="/tmp/new.html",
            content_diff="+ added line\n- removed line",
        )
        self.assertEqual(result.fromfile, "/tmp/old.html")
        self.assertEqual(result.tofile, "/tmp/new.html")
        self.assertIn("added line", result.content_diff)

    def test_rejects_binary_http_result(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={"content-type": "image/png"},
            is_binary=True,
            size=100,
            body_file="/tmp/img.bin",
        )
        with self.assertRaises(ValueError):
            HttpTextDiffToolResult(
                http_result=http_result,
                fromfile="/tmp/old.html",
                tofile="/tmp/new.html",
                content_diff="diff",
            )

    def test_rejects_relative_path(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={},
            is_binary=False,
            size=0,
            body="",
        )
        with self.assertRaises(ValueError):
            HttpTextDiffToolResult(
                http_result=http_result,
                fromfile="relative/old.html",
                tofile="/tmp/new.html",
                content_diff="diff",
            )
        with self.assertRaises(ValueError):
            HttpTextDiffToolResult(
                http_result=http_result,
                fromfile="/tmp/old.html",
                tofile="relative/new.html",
                content_diff="diff",
            )

    def test_rejects_long_diff(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={},
            is_binary=False,
            size=0,
            body="",
        )
        long_diff = "x" * 10000
        with self.assertRaises(ValueError):
            HttpTextDiffToolResult(
                http_result=http_result,
                fromfile="/tmp/old.html",
                tofile="/tmp/new.html",
                content_diff=long_diff,
            )

    def test_9999_char_diff_ok(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={},
            is_binary=False,
            size=0,
            body="",
        )
        diff_9999 = "x" * 9999
        result = HttpTextDiffToolResult(
            http_result=http_result,
            fromfile="/tmp/old.html",
            tofile="/tmp/new.html",
            content_diff=diff_9999,
        )
        self.assertEqual(len(result.content_diff), 9999)

    def test_to_json_and_from_json(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={"x": "y"},
            is_binary=False,
            size=13,
            body="hello world",
        )
        result = HttpTextDiffToolResult(
            http_result=http_result,
            fromfile="/tmp/old.html",
            tofile="/tmp/new.html",
            content_diff="+ added",
        )
        json_str = result.to_json()
        restored = HttpTextDiffToolResult.from_json(json_str)
        self.assertEqual(restored.fromfile, "/tmp/old.html")
        self.assertEqual(restored.tofile, "/tmp/new.html")
        self.assertEqual(restored.content_diff, "+ added")
        self.assertEqual(restored.http_result.body, "hello world")

    def test_to_llm_content(self):
        http_result = HttpToolResult(
            status_code=200,
            headers={"content-type": "text/plain"},
            is_binary=False,
            size=10,
            body="test body",
        )
        result = HttpTextDiffToolResult(
            http_result=http_result,
            fromfile="/tmp/old.html",
            tofile="/tmp/new.html",
            content_diff="+ added line",
        )
        content = result.to_llm_content()
        self.assertIn("<<body_diff>>", content)
        self.assertIn("<<fromfile>>/tmp/old.html<<fromfile>>", content)
        self.assertIn("<<tofile>>/tmp/new.html<<tofile>>", content)
        self.assertIn("<<content_diff>>+ added line<<content_diff>>", content)
        self.assertIn("test body", content)


if __name__ == "__main__":
    unittest.main()
