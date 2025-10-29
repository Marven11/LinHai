import unittest
from unittest.mock import patch, mock_open
import tomllib

# 使用测试代码中的精确配置内容
config_content = b'''[[llm]]
name = "primary"
base_url = "https://api.example.com"
api_key = "test_key"
model = "test_model"'''

# 只mock linhai.config模块中的文件读取
with patch('linhai.config.tomllib.load') as mock_tomllib_load:
    # 模拟tomllib.load返回正确的配置数据
    mock_tomllib_load.return_value = {
        'llm': [
            {
                'name': 'primary',
                'base_url': 'https://api.example.com',
                'api_key': 'test_key',
                'model': 'test_model'
            }
        ]
    }
    
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