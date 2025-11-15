"""测试流式JSON解析器的数组元素编号功能"""
import unittest
from linhai.streamjson.main import StreamJsonParser


class TestStreamJsonArrayIndexing(unittest.TestCase):
    """测试数组元素编号是否正确递增"""

    def test_array_indexing(self):
        """测试基础数组索引功能"""
        parser = StreamJsonParser()
        json_str = '{"arr": ["a", "b"]}'
        
        # 分块输入JSON字符串
        results = []
        for i in range(0, len(json_str), 2):
            parser.feed_string(json_str[i:i+2])
            for value in parser:
                if hasattr(value, 'value'):  # 只处理完整的Value对象
                    results.append((value.index_key, value.value))
        
        # 验证数组元素的索引键
        expected_keys = ["arr.0", "arr.1"]
        actual_keys = [key for key, value in results if key.startswith("arr.")]
        
        self.assertEqual(actual_keys, expected_keys, 
                        f"数组索引键不正确，期望{expected_keys}，实际得到{actual_keys}")

    def test_nested_array_indexing(self):
        """测试嵌套数组索引功能"""
        parser = StreamJsonParser()
        json_str = '{"nested": {"inner_arr": ["x", "y", "z"]}}'
        
        results = []
        for i in range(0, len(json_str), 3):
            parser.feed_string(json_str[i:i+3])
            for value in parser:
                if hasattr(value, 'value'):  # 只处理完整的Value对象
                    results.append((value.index_key, value.value))
        
        # 验证嵌套数组元素的索引键
        expected_keys = ["nested.inner_arr.0", "nested.inner_arr.1", "nested.inner_arr.2"]
        actual_keys = [key for key, value in results if key.startswith("nested.inner_arr.")]
        
        self.assertEqual(actual_keys, expected_keys,
                        f"嵌套数组索引键不正确，期望{expected_keys}，实际得到{actual_keys}")

    def test_mixed_array_object(self):
        """测试混合对象和数组的索引"""
        parser = StreamJsonParser()
        json_str = '{"data": [{"name": "李田所"}, {"age": 24}]}'
        
        results = []
        for i in range(0, len(json_str), 4):
            parser.feed_string(json_str[i:i+4])
            for value in parser:
                if hasattr(value, 'value'):  # 只处理完整的Value对象
                    results.append((value.index_key, value.value))
        
        # 验证混合结构的索引键
        expected_keys = ["data.0.name", "data.1.age"]
        actual_keys = [key for key, value in results if "." in key and not key.endswith("data")]
        
        self.assertEqual(sorted(actual_keys), sorted(expected_keys),
                        f"混合结构索引键不正确，期望{expected_keys}，实际得到{actual_keys}")


if __name__ == "__main__":
    unittest.main()