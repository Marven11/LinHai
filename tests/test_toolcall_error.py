import unittest
from linhai.tui.components import ToolCallWidget
from linhai.parsed_message import ToolCallSegment


def _make_toolcall_segment() -> ToolCallSegment:
    return ToolCallSegment(
        segment_type="toolcall",
        raw="",
        is_finished=False,
        is_corrupted=False,
        markdown_representation="",
        tool_name="",
    )


class TestToolCallErrorHandling(unittest.TestCase):
    def test_invalid_json_display_error(self):
        invalid_json = '{"name": "test", "args": {missing_quote: "value"}'
        segment = _make_toolcall_segment()
        segment["raw"] = invalid_json
        segment["is_corrupted"] = True
        segment["markdown_representation"] = "<bad toolcall>"

        widget = ToolCallWidget(
            config_theme="nord", segment=segment, get_refresh_interval=lambda: 0.05
        )
        widget.update_display()

        self.assertTrue(widget.has_error)

    def test_valid_json_no_error(self):
        valid_json = '{"name": "test_tool", "arguments": {"param": "value"}}'
        segment = _make_toolcall_segment()
        segment["raw"] = valid_json
        segment["markdown_representation"] = (
            '- name: `test_tool`\n- arguments: `{"param": "value"}`\n'
        )
        segment["tool_name"] = "test_tool"

        widget = ToolCallWidget(
            config_theme="nord", segment=segment, get_refresh_interval=lambda: 0.05
        )
        widget.update_display()

        self.assertFalse(widget.has_error)


if __name__ == "__main__":
    unittest.main()
