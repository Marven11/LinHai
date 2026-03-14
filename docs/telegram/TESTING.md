# 测试文档

## 测试策略

为 issue #23 的 Telegram 同步脚本功能设计测试时，应遵循以下原则：

### 1. 使用 unittest 而非 pytest

**重要：本项目使用 Python 的 unittest 模块进行测试，不使用 pytest。**

所有测试文件必须以 unittest 格式编写，示例：

```python
import unittest
from unittest.mock import Mock, patch
from telegram import Bot, Message, Chat, User

class TestTelegramBot(unittest.TestCase):
    def setUp(self):
        self.bot = Bot(token="test_token")
        self.chat = Chat(id=123, type="private")
        
    def test_send_message(self):
        with patch.object(self.bot, 'send_message') as mock_send:
            self.bot.send_message(chat_id=123, text="Hello")
            mock_send.assert_called_once_with(chat_id=123, text="Hello")

if __name__ == "__main__":
    unittest.main()
```

### 2. 测试覆盖范围

应测试以下核心功能：

1. **配置加载** - Telegram 配置项的正确解析
2. **消息处理** - 接收和发送消息的基本流程
3. **错误处理** - 网络错误、认证失败等异常情况
4. **插件集成** - 与 LinHai 现有系统的集成
5. **异步操作** - 使用 asyncio 的异步测试

### 3. 测试示例

以下是从 python-telegram-bot 项目选择的五个测试示例，已转换为 unittest 格式或保留原始格式作为参考：

#### 示例 1: BotCommand 测试 (已转换)

见 `test_botcommand.py`，已从 pytest 转换为 unittest 格式。

#### 示例 2: CallbackQuery 测试 (参考格式)

见 `test_callbackquery.py`，保留原始 pytest 格式作为参考，实际使用时应转换为 unittest。

#### 示例 3: Chat 对象测试

原始测试文件过大，仅保留核心测试方法：

```python
# test_chat.py 简化示例
class TestChat(unittest.TestCase):
    def test_chat_creation(self):
        chat = Chat(id=123, type="private")
        self.assertEqual(chat.id, 123)
        self.assertEqual(chat.type, "private")
        
    def test_chat_equality(self):
        chat1 = Chat(id=123, type="private")
        chat2 = Chat(id=123, type="private")
        chat3 = Chat(id=456, type="group")
        
        self.assertEqual(chat1, chat2)
        self.assertNotEqual(chat1, chat3)
```

#### 示例 4: ChatMember 测试

```python
# test_chatmember.py 简化示例
class TestChatMember(unittest.TestCase):
    def test_member_status(self):
        from telegram import ChatMemberOwner
        
        owner = ChatMemberOwner(
            user=User(id=1, is_bot=False, first_name="Owner"),
            status="creator",
            is_anonymous=False
        )
        
        self.assertEqual(owner.status, "creator")
        self.assertFalse(owner.is_anonymous)
```

#### 示例 5: Bot 核心功能测试

```python
# test_bot.py 简化示例
class TestBotCore(unittest.TestCase):
    def setUp(self):
        self.bot = Bot(token="test_token")
        
    @patch('telegram.Bot._post')
    def test_get_me(self, mock_post):
        mock_post.return_value = {"id": 123, "is_bot": True, "first_name": "TestBot"}
        
        user = self.bot.get_me()
        
        self.assertEqual(user.id, 123)
        self.assertTrue(user.is_bot)
        self.assertEqual(user.first_name, "TestBot")
```

### 4. 测试运行命令

运行所有测试：
```bash
python -m unittest discover tests/
```

运行特定测试文件：
```bash
python -m unittest tests.test_telegram
```

### 5. 测试依赖

- `unittest` - Python 标准库
- `unittest.mock` - 用于模拟对象
- `asyncio` - 异步测试支持
- `telegram` - python-telegram-bot 库

### 6. 注意事项

1. **避免使用 pytest 特定功能**：如 fixture、parametrize 等
2. **使用 unittest.mock 进行模拟**：而不是 pytest-mock
3. **异步测试使用 unittest.IsolatedAsyncioTestCase**：

```python
import asyncio
from unittest import IsolatedAsyncioTestCase

class TestAsyncTelegram(IsolatedAsyncioTestCase):
    async def test_async_message(self):
        # 异步测试代码
        result = await some_async_function()
        self.assertEqual(result, expected)
```

## 版权声明

本测试文档基于 python-telegram-bot 项目的测试代码编写，原始版权归该项目所有。

原始版权声明：
```
A library that provides a Python interface to the Telegram Bot API
Copyright (C) 2015-2026
Leandro Toledo de Souza <devs@python-telegram-bot.org>
```