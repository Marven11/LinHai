from linhai.parsed_message import (
    OpenAiToolCallFeeder,
    OpenAiToolCallSegment,
    BAD_TOOLCALL,
)


def _make_segment() -> OpenAiToolCallSegment:
    return OpenAiToolCallSegment(
        segment_type="openai_toolcall",
        idx=0,
        id="call_123",
        raw="",
        is_finished=False,
        is_corrupted=False,
        markdown_representation="",
        tool_name="",
    )


def test_feeder_empty_args():
    segment = _make_segment()
    segment["tool_name"] = "get_weather"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed("{}")
    assert segment["markdown_representation"] == "get_weather:"
    assert segment["raw"] == "{}"
    assert not segment["is_corrupted"]


def test_feeder_simple_args():
    segment = _make_segment()
    segment["tool_name"] = "get_weather"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"location": "Tokyo", "unit": "celsius"}')
    assert segment["is_finished"] is False
    assert not segment["is_corrupted"]
    md = segment["markdown_representation"]
    assert md.startswith("get_weather:\n\n")
    assert "- location: `Tokyo`" in md
    assert "- unit: `celsius`" in md


def test_feeder_streaming_chunks():
    segment = _make_segment()
    segment["tool_name"] = "search"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"qu')
    feeder.feed('ery": "h')
    feeder.feed('ello"}')
    assert not segment["is_corrupted"]
    md = segment["markdown_representation"]
    assert md.startswith("search:\n\n")
    assert "- query: `hello`" in md


def test_feeder_corrupted_json():
    segment = _make_segment()
    segment["tool_name"] = "bad_tool"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed("not json at all{{{")
    assert segment["is_corrupted"] is True
    assert segment["markdown_representation"] == BAD_TOOLCALL


def test_feeder_multiline_value():
    segment = _make_segment()
    segment["tool_name"] = "execute"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"code": "line1\\nline2\\nline3"}')
    md = segment["markdown_representation"]
    assert md.startswith("execute:\n\n")
    assert "line1" in md


def test_feeder_finish():
    segment = _make_segment()
    segment["tool_name"] = "test"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed("{}")
    feeder.finish()
    assert segment["is_finished"] is True


def test_feeder_no_tool_name_shows_unknown():
    segment = _make_segment()
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed("{}")
    assert "\u672a\u77e5\u5de5\u5177" in segment["markdown_representation"]


def test_refresh_tool_name():
    segment = _make_segment()
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"key": "value"}')
    assert "\u672a\u77e5\u5de5\u5177" in segment["markdown_representation"]
    segment["tool_name"] = "my_tool"
    feeder.refresh_tool_name()
    assert segment["markdown_representation"].startswith("my_tool:")


def test_refresh_tool_name_corrupted():
    segment = _make_segment()
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed("not json{{")
    assert segment["is_corrupted"]
    segment["tool_name"] = "tool"
    feeder.refresh_tool_name()
    assert segment["markdown_representation"] == BAD_TOOLCALL


def test_feeder_numeric_value():
    segment = _make_segment()
    segment["tool_name"] = "calc"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"count": 42, "ratio": 3.14}')
    md = segment["markdown_representation"]
    assert "- count: `42`" in md
    assert "- ratio: `3.14`" in md


def test_feeder_boolean_value():
    segment = _make_segment()
    segment["tool_name"] = "toggle"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"enabled": true, "visible": false}')
    md = segment["markdown_representation"]
    assert "- enabled: `true`" in md
    assert "- visible: `false`" in md


def test_feeder_nested_value():
    segment = _make_segment()
    segment["tool_name"] = "config"
    feeder = OpenAiToolCallFeeder(segment)
    feeder.feed('{"settings": {"a": 1}}')
    md = segment["markdown_representation"]
    assert "- settings.a: `1`" in md
