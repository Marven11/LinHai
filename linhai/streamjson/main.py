"""
流式json解析器，每次向解析器中传入一块chunk后可以流式地读取新的值

这个解析器会将json解析为类似以下人类可读机器不可读键值对的形式

name = 李田所
age = 24
preference.0 = "王道征途"
preference.1 = "泡泡浴"
number_decode.iiyo = 114
number_decode.hato = 810
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import time
import json
import re
import codecs

PAIRS = {"}": "{", "]": "["}
ESCAPED = re.compile(r'^\\([ntr\\"]|x[a-fA-F0-9]{2}|u[a-fA-F0-9]{4}|U[a-fA-F0-9]{8})')


class ParserState(Enum):
    """解析器状态枚举"""

    OUTSIDE = "outside"
    KEY = "key"
    ATOMIC_VALUE = "atomic-value"
    STRING_VALUE = "string-value"
    INVALID = "invalid"


@dataclass
class ValuePiece:
    """字符串值的单个字符片段"""

    index_key: str
    char: str


@dataclass
class Value:
    """完整的解析值"""

    index_key: str
    value: str | int | float | bool | None


def is_atomic_value_char(c: str) -> bool:
    """检查字符是否为原子值起始字符"""
    assert len(c) == 1
    return c in "0123456789truefalsenull"


def is_whitespace(c: str) -> bool:
    """检查字符是否为空白字符"""
    return c in " \n\t\r"


class StreamJsonStringParser:
    """解析JSON字符串双引号内的数据，处理转义字符"""

    def __init__(self):
        self.remains = ""

    def feed_char(self, c: str):
        """输入单个字符"""
        assert len(c) == 1
        self.remains += c

    def get_escaped_char(self) -> str | bool:
        """获取转义字符或判断字符串是否结束"""
        if not self.remains:
            return False

        c = self.remains[0]
        if c == '"':
            return True
        if c != "\\":
            self.remains = self.remains[1:]
            return c

        if result := ESCAPED.match(self.remains):
            length = len(result.group(0))
            c = codecs.decode(self.remains[:length], "unicode_escape")
            self.remains = self.remains[length:]
            return c

        if len(self.remains) >= 2 and self.remains[1] not in 'xuU\\"':
            c = self.remains[1]
            self.remains = self.remains[2:]
            return c

        return False


class StreamJsonParser:
    """流式JSON解析器主类"""

    def __init__(self):
        self.state: ParserState = ParserState.OUTSIDE
        self.stack: list[str | int] = []
        self.toyield = []
        self.payload = ""
        self.payload_string_parser: StreamJsonStringParser | None = None
        self.started = False

    def is_current_data_finished(self):
        return self.started and not self.stack

    def calculate_current_index_key(self) -> str:
        """计算当前键的索引路径"""
        current = self.stack.copy()
        result = []
        while current:
            match current.pop(0):
                case "[":
                    key = current.pop(0)
                    assert isinstance(key, int)
                    result.append(str(key))
                case "{":
                    key = current.pop(0)
                    assert isinstance(key, str)
                    key_repr = (
                        key if re.match("^[0-9a-zA-Z-_]", key) else json.dumps(key)
                    )
                    result.append(key_repr)
        return ".".join(result)

    def _handle_brackets(self, c: str):
        """处理括号字符"""
        if c in "{[":
            self.stack.append(c)
        elif c in "}]":
            if not self.stack:
                self.state = ParserState.INVALID
                raise RuntimeError("Stack is empty")
            pair = self.stack.pop()
            if pair != PAIRS[c]:
                self.state = ParserState.INVALID
                raise RuntimeError(f"Bracket mismatch: {pair!r} != {PAIRS[c]!r}")
            if self.stack:
                used_key_index = self.stack.pop()
                assert used_key_index not in ["{", "["]

    def _handle_inside_object_value(self, c: str):
        """处理对象内部的值"""
        if c == '"':
            self.payload = '"'
            self.state = ParserState.STRING_VALUE
        elif is_atomic_value_char(c):
            self.payload += c
            self.state = ParserState.ATOMIC_VALUE
        else:
            self.state = ParserState.INVALID
            raise RuntimeError(f"Unrecognized character: {c!r}")

    def feed_char_outside(self, c: str):
        """处理外部状态字符"""
        assert len(c) == 1
        current_top = self.stack[-1] if self.stack else None

        # 处理括号
        if c in "{}[]":
            self._handle_brackets(c)
            return

        # 处理空白字符
        if is_whitespace(c):
            return

        self.started = True

        # 处理逗号
        if c == "," and current_top in ["{", "["]:
            return

        # 处理对象中的冒号
        if (
            c == ":"
            and isinstance(current_top, str)
            and len(self.stack) >= 2
            and self.stack[-2] == "{"
        ):
            return

        # 处理键
        if current_top == "{" and c == '"':
            self.payload += c
            self.state = ParserState.KEY
            return

        # 处理数组中的值
        if current_top == "[":
            if c == '"':
                self.stack.append(0)
                self.payload = '"'
                self.state = ParserState.STRING_VALUE
            elif is_atomic_value_char(c):
                self.stack.append(0)
                self.payload = c
                self.state = ParserState.ATOMIC_VALUE
            else:
                self.state = ParserState.INVALID
                raise RuntimeError(f"数组值起始字符无效: {c!r}")
            return

        # 处理对象内部的值
        is_inside_object = (
            len(self.stack) >= 2
            and self.stack[-2] == "{"
            and isinstance(current_top, str)
        )
        if is_inside_object:
            self._handle_inside_object_value(c)
            return

        self.state = ParserState.INVALID
        raise RuntimeError(f"无法识别字符: {c!r} 在状态 {self.state.value}")

    def feed_char_key(self, c: str):
        """处理键状态字符"""
        assert len(c) == 1
        assert self.payload != "" and self.payload[0] == '"'

        backslash_count = len(self.payload) - len(self.payload.rstrip("\\"))

        if c == '"' and backslash_count % 2 == 0:
            payload = self.payload + c
            self.stack.append(json.loads(payload))
            self.payload = ""
            self.state = ParserState.OUTSIDE
        else:
            self.payload += c

    def feed_char_atomic_value(self, c: str):
        """处理原子值状态字符"""
        assert len(c) == 1

        index_key = self.calculate_current_index_key()

        if not is_atomic_value_char(c):
            value = json.loads(self.payload)
            self.payload = ""
            self.toyield.append(Value(index_key=index_key, value=value))
            self.stack.pop()
            self.state = ParserState.OUTSIDE
            self.feed_char(c)
        else:
            self.payload += c

    def feed_char_string_value(self, c: str):
        """处理字符串值状态字符"""
        if self.payload_string_parser is None:
            self.payload_string_parser = StreamJsonStringParser()

        self.payload_string_parser.feed_char(c)
        self.payload += c

        index_key = self.calculate_current_index_key()
        parsed = self.payload_string_parser.get_escaped_char()

        if isinstance(parsed, str):
            self.toyield.append(ValuePiece(index_key=index_key, char=parsed))
            return

        is_string_ended: bool = parsed
        if is_string_ended:
            value = json.loads(self.payload)
            self.toyield.append(Value(index_key=index_key, value=value))
            self.stack.pop()
            self.state = ParserState.OUTSIDE
            self.payload_string_parser = None
            self.payload = ""

    def feed_char(self, c: str):
        """输入单个字符进行解析"""
        assert len(c) == 1

        state_handlers = {
            ParserState.OUTSIDE: self.feed_char_outside,
            ParserState.KEY: self.feed_char_key,
            ParserState.STRING_VALUE: self.feed_char_string_value,
            ParserState.ATOMIC_VALUE: self.feed_char_atomic_value,
        }

        if self.state in state_handlers:
            state_handlers[self.state](c)
        else:
            raise RuntimeError("Invalid parser state")

    def feed_string(self, s: str):
        """输入字符串进行解析"""
        for c in s:
            self.feed_char(c)

    def __iter__(self):
        return self

    def __next__(self) -> Value | ValuePiece:
        if not self.toyield:
            raise StopIteration()
        return self.toyield.pop(0)


def example1():
    """示例1：基础解析演示"""
    parser = StreamJsonParser()
    payload = """
{
    "name": "李田所",
    "age": 24,
    "preference": [
        "王道征途",
        "\\u6ce1\\u6ce1\\u6d74",
    ],
    "number_decode": {
        "iiyo": 114,
        "hato": 810
    }
}
"""
    for i in range(0, len(payload), 4):
        parser.feed_string(payload[i : i + 4])
        for c in parser:
            print(f"{c.index_key}={c}")


def example2():
    """示例2：文件解析演示"""
    parser = StreamJsonParser()
    payload = Path("test.json").read_text(encoding="utf-8")
    result = {}
    for i in range(0, len(payload), 4):
        parser.feed_string(payload[i : i + 4])
        for c in parser:
            if c.index_key not in result:
                print(f"{c.index_key} = ", end="", flush=True)
                result[c.index_key] = ""
            if isinstance(c, ValuePiece):
                result[c.index_key] += c.char
                print(c.char, end="", flush=True)
            else:
                if isinstance(c.value, str):
                    assert c.value == result[c.index_key]
                    print()
                else:
                    print(c.value)
                result[c.index_key] = c.value
        time.sleep(0.1)
    print(result)


def main():
    example1()
    example2()
