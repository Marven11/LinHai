#!/usr/bin/env python3
"""
简单的MCP服务器示例，实现a+b功能
基于Model Context Protocol (MCP) 规范
"""

import json
import sys
import asyncio
from typing import Any, Dict, List


class MCPServer:
    def __init__(self):
        self.tools = [
            {
                "name": "add",
                "description": "计算两个数字的和",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {
                            "type": "number",
                            "description": "第一个数字"
                        },
                        "b": {
                            "type": "number", 
                            "description": "第二个数字"
                        }
                    },
                    "required": ["a", "b"]
                }
            }
        ]

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理MCP请求"""
        method = request.get("method")
        request_id = request.get("id")
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "simple-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": self.tools
                }
            }
        
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "add":
                a = arguments.get("a", 0)
                b = arguments.get("b", 0)
                result = a + b
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"工具 '{tool_name}' 未找到"
                    }
                }
        
        elif method == "notifications/initialized":
            # 忽略初始化通知
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": None
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"方法 '{method}' 未找到"
                }
            }


async def main():
    """主函数，处理stdio通信"""
    server = MCPServer()
    
    # 从stdin读取，写入stdout
    while True:
        try:
            # 读取一行输入
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
                
            # 解析JSON请求
            request = json.loads(line.strip())
            
            # 处理请求
            response = await server.handle_request(request)
            
            # 发送响应
            if response:
                response_json = json.dumps(response)
                sys.stdout.write(response_json + "\n")
                sys.stdout.flush()
                
        except json.JSONDecodeError:
            # 无效的JSON，发送错误响应
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "解析错误"
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()
        except Exception as e:
            # 其他错误
            error_response = {
                "jsonrpc": "2.0", 
                "id": None,
                "error": {
                    "code": -32603,
                    "message": f"内部错误: {str(e)}"
                }
            }
            sys.stdout.write(json.dumps(error_response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())