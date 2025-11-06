#!/usr/bin/env python3
"""测试MCP服务器的简单脚本"""

import asyncio
import json
import subprocess
import sys


async def test_mcp_server():
    """测试MCP服务器"""
    # 启动MCP服务器进程
    process = await asyncio.create_subprocess_exec(
        sys.executable, "mcp_server_example.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    async def send_request(request):
        """发送请求到服务器并返回响应"""
        request_json = json.dumps(request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()
        
        # 读取响应
        line = await process.stdout.readline()
        return json.loads(line.decode().strip())
    
    try:
        # 测试初始化
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                },
                "capabilities": {}
            }
        }
        
        init_response = await send_request(init_request)
        print("初始化响应:", init_response)
        
        # 测试工具列表
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        list_response = await send_request(list_request)
        print("工具列表响应:", list_response)
        
        # 测试工具调用
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add",
                "arguments": {
                    "a": 5,
                    "b": 3
                }
            }
        }
        
        call_response = await send_request(call_request)
        print("工具调用响应:", call_response)
        
        # 验证结果
        result_text = call_response["result"]["content"][0]["text"]
        expected = "8"
        if result_text == expected:
            print(f"✅ 测试通过: 5 + 3 = {result_text}")
        else:
            print(f"❌ 测试失败: 期望 {expected}, 得到 {result_text}")
            
    finally:
        # 清理进程
        process.terminate()
        await process.wait()


if __name__ == "__main__":
    asyncio.run(test_mcp_server())