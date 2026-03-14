# Telegram 同步脚本文档

## 概述

本目录包含为 issue #23 准备的 Telegram 同步脚本相关文档和示例代码。issue #23 的目标是为 LinHai 项目添加 Telegram bot 功能，实现消息同步和处理能力。

## 文件结构

- `README.md` - 本文件，概述文档
- `TESTING.md` - 测试相关文档，包含从 python-telegram-bot 项目选择的测试示例
- `IMPLEMENTATION.md` - 实现细节文档，包括配置项和插件设计
- `test_botcommand.py` - BotCommand 类测试示例（已从 pytest 格式转换）
- `test_callbackquery.py` - CallbackQuery 类测试示例（pytest 格式，仅供参考）
- `test_chat.py` - Chat 类测试示例（待添加）
- `test_chatmember.py` - ChatMember 类测试示例（待添加）
- `test_bot.py` - Bot 类核心功能测试示例（待添加）

## 版权信息

本目录中的测试代码基于 python-telegram-bot 项目的测试文件修改而来，原始版权归 python-telegram-bot 项目所有。

原始版权声明：
```
A library that provides a Python interface to the Telegram Bot API
Copyright (C) 2015-2026
Leandro Toledo de Souza <devs@python-telegram-bot.org>
```

## 重要警告

**本项目不使用 pytest**

所有测试代码都需要使用 Python 的 unittest 模块运行，而不是 pytest。提供的测试示例中，部分已转换为 unittest 格式，部分仍保留 pytest 格式作为参考。在实际实现中，请确保使用 unittest 编写测试。

## 相关 issue

- **issue #23**: 添加 Telegram 同步脚本功能
- **issue #83**: 为 issue #23 准备文档（本目录）

## 使用说明

1. 配置 Telegram bot token 到 LinHai 配置文件中
2. 实现 telegram.py 插件，处理消息接收和发送
3. 参考本目录中的测试示例编写单元测试
4. 使用 `python -m unittest` 运行测试

## 快速开始

以下是一个简单的 Telegram bot 配置示例：

```toml
# config.toml 中添加
[telegram]
token = "YOUR_BOT_TOKEN"
chat_id = "YOUR_CHAT_ID"
enabled = true
```

对应的 Python 实现示例：

```python
# telegram.py
import asyncio
from telegram import Bot
from telegram.ext import Application

class TelegramPlugin:
    def __init__(self, config):
        self.token = config['telegram']['token']
        self.chat_id = config['telegram']['chat_id']
        self.bot = None
        
    async def start(self):
        self.bot = Bot(token=self.token)
        # 初始化消息处理等
        
    async def send_message(self, text):
        if self.bot:
            await self.bot.send_message(chat_id=self.chat_id, text=text)
```

## 下一步

1. 阅读 `IMPLEMENTATION.md` 了解详细实现设计
2. 查看 `TESTING.md` 了解测试策略
3. 参考测试示例编写实际代码