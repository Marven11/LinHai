import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from linhai.tool.tools.http import fetch_article

async def test_direct():
    print("开始直接调用fetch_article工具")
    try:
        # 直接调用fetch_article工具
        result = await asyncio.wait_for(fetch_article("https://news.ycombinator.com/item?id=45657428"), timeout=30)
        print(f"工具调用成功: {result[:200]}...")
    except asyncio.TimeoutError:
        print("工具调用超时")
    except Exception as e:
        print(f"工具调用异常: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct())