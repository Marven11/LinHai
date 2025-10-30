#!/usr/bin/env python3
import time
import sys
import os

print(f"Python executable: {sys.executable}")
print(f"Python path: {sys.path}")
print(f"Current directory: {os.getcwd()}")

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Starting minimal import test...")
start_time = time.time()

try:
    # 尝试导入基本模块
    print("1. Importing basic modules...")
    import json
    import asyncio
    print("   Basic modules imported successfully")
    
    print("2. Importing linhai base modules...")
    from linhai.agent_base import RuntimeMessage
    print("   linhai.agent_base imported successfully")
    
    print("3. Importing linhai tool modules...")
    from linhai.tool.base import global_tools
    print("   linhai.tool.base imported successfully")
    
    print("4. Importing fetch_article tool...")
    from linhai.tool.tools.http import fetch_article
    print("   fetch_article imported successfully")
    
    print("5. Testing direct function call...")
    # 测试直接调用函数（不通过linhai框架）
    result = fetch_article("https://news.ycombinator.com/item?id=45657428")
    print(f"   Direct call result: {result[:100]}...")
    
    end_time = time.time()
    print(f"All imports and tests completed in {end_time - start_time:.2f} seconds")
    
except Exception as e:
    end_time = time.time()
    print(f"Error occurred after {end_time - start_time:.2f} seconds: {e}")
    import traceback
    traceback.print_exc()