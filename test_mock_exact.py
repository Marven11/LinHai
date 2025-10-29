import unittest
from unittest.mock import patch, mock_open
import tomllib

# 使用测试代码中的精确配置内容
config_content = b'''[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"'''

# 使用与测试代码相同的mock设置
with patch('pathlib.Path.open', mock_open(read_data=config_content)) as mock_file:
    # 模拟测试代码中的设置
    mock_file.return_value.__enter__ = mock_file.return_value
    mock_file.return_value.__exit__ = lambda self, *args: None
    mock_file.return_value.read.return_value = config_content
    
    # 导入并调用load_config
    from linhai.config import load_config
    try:
        config = load_config()
        print('Mock测试成功')
        print('LLM数量:', len(config.llm))
        print('第一个LLM名称:', config.llm[0].name)
    except Exception as e:
        print('Mock测试失败:', e)
        import traceback
        traceback.print_exc()