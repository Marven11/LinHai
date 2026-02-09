from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio


class RemoteControlInterface(ABC):
    @abstractmethod
    async def connect(self) -> bool:
        """建立远程连接。

        Returns:
            连接是否成功
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """关闭远程连接并清理资源。"""
        pass

    @abstractmethod
    async def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """发送JSON-RPC请求并返回响应。

        Args:
            method: 方法名
            params: 参数

        Returns:
            JSON-RPC响应
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查连接是否有效。

        Returns:
            连接是否有效
        """
        pass

    @abstractmethod
    async def wait_for_disconnect(self):
        """等待连接断开。"""
        pass
