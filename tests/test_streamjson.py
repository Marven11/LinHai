"""测试流式JSON解析器的数组元素编号功能"""

import unittest
from linhai.streamjson.main import StreamJsonParser, Value


class TestStreamJsonArrayIndexing(unittest.TestCase):
    """测试数组元素编号是否正确递增"""

    def test_array_indexing(self):
        """测试基础数组索引功能"""
        parser = StreamJsonParser()
        json_str = '{"arr": ["a", "b"]}'

        results = []
        for i in range(0, len(json_str), 2):
            parser.feed_string(json_str[i : i + 2])
            for value in parser:
                if isinstance(value, Value):  # 只处理完整的Value对象
                    results.append((value.index_key, value.value))

        expected_keys = ["arr.0", "arr.1"]
        actual_keys = [key for key, value in results if key.startswith("arr.")]

        self.assertEqual(
            actual_keys,
            expected_keys,
            f"数组索引键不正确，期望{expected_keys}，实际得到{actual_keys}",
        )

    def test_nested_array_indexing(self):
        """测试嵌套数组索引功能"""
        parser = StreamJsonParser()
        json_str = '{"nested": {"inner_arr": ["x", "y", "z"]}}'

        results = []
        for i in range(0, len(json_str), 3):
            parser.feed_string(json_str[i : i + 3])
            for value in parser:
                if isinstance(value, Value):  # 只处理完整的Value对象
                    results.append((value.index_key, value.value))

        expected_keys = [
            "nested.inner_arr.0",
            "nested.inner_arr.1",
            "nested.inner_arr.2",
        ]
        actual_keys = [
            key for key, value in results if key.startswith("nested.inner_arr.")
        ]

        self.assertEqual(
            actual_keys,
            expected_keys,
            f"嵌套数组索引键不正确，期望{expected_keys}，实际得到{actual_keys}",
        )

    def test_mixed_array_object(self):
        """测试混合对象和数组的索引"""
        parser = StreamJsonParser()
        json_str = '{"data": [{"name": "李田所"}, {"age": 24}]}'

        results = []
        for i in range(0, len(json_str), 4):
            parser.feed_string(json_str[i : i + 4])
            for value in parser:
                if isinstance(value, Value):  # 只处理完整的Value对象
                    results.append((value.index_key, value.value))

        expected_keys = ["data.0.name", "data.1.age"]
        actual_keys = [
            key for key, value in results if "." in key and not key.endswith("data")
        ]

        self.assertEqual(
            sorted(actual_keys),
            sorted(expected_keys),
            f"混合结构索引键不正确，期望{expected_keys}，实际得到{actual_keys}",
        )


if __name__ == "__main__":
    unittest.main()


class TestStreamJsonNumberSupport(unittest.TestCase):
    """测试数字支持，包括负数和小数"""

    def test_negative_numbers(self):
        """测试负数解析"""
        parser = StreamJsonParser()
        json_str = '{"negative": -114514}'

        results = []
        for i in range(0, len(json_str), 2):
            parser.feed_string(json_str[i : i + 2])
            for value in parser:
                if isinstance(value, Value):
                    results.append((value.index_key, value.value))

        expected = ("negative", -114514)
        actual = next(((k, v) for k, v in results if k == "negative"), None)
        self.assertEqual(
            actual, expected, f"负数解析失败，期望{expected}，实际得到{actual}"
        )

    def test_float_numbers(self):
        """测试小数解析"""
        parser = StreamJsonParser()
        json_str = '{"float": 3.14159}'

        results = []
        for i in range(0, len(json_str), 2):
            parser.feed_string(json_str[i : i + 2])
            for value in parser:
                if isinstance(value, Value):
                    results.append((value.index_key, value.value))

        expected = ("float", 3.14159)
        actual = next(((k, v) for k, v in results if k == "float"), None)
        self.assertEqual(
            actual, expected, f"小数解析失败，期望{expected}，实际得到{actual}"
        )

    def test_negative_float(self):
        """测试负小数解析"""
        parser = StreamJsonParser()
        json_str = '{"neg_float": -2.718}'

        results = []
        for i in range(0, len(json_str), 2):
            parser.feed_string(json_str[i : i + 2])
            for value in parser:
                if isinstance(value, Value):
                    results.append((value.index_key, value.value))

        expected = ("neg_float", -2.718)
        actual = next(((k, v) for k, v in results if k == "neg_float"), None)
        self.assertEqual(
            actual, expected, f"负小数解析失败，期望{expected}，实际得到{actual}"
        )

    def test_mixed_numbers(self):
        """测试混合数字类型"""
        parser = StreamJsonParser()
        json_str = '{"numbers": [114, -514, 3.14, -2.718]}'

        results = []
        for i in range(0, len(json_str), 3):
            parser.feed_string(json_str[i : i + 3])
            for value in parser:
                if isinstance(value, Value):
                    results.append((value.index_key, value.value))

        expected_values = [114, -514, 3.14, -2.718]
        actual_values = [v for k, v in results if k.startswith("numbers.")]
        self.assertEqual(
            actual_values,
            expected_values,
            f"混合数字解析失败，期望{expected_values}，实际得到{actual_values}",
        )
