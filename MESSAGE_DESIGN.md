# LinHai Message 架构设计

## 概述

LinHai 的消息系统基于协议和类层次结构，支持不同类型的消息（系统消息、聊天消息、工具调用消息等），并能够将这些消息转换为 LLM 可以理解的格式。

## 核心协议

### Message 协议

`Message` 是一个运行时检查协议（使用 `@runtime_checkable` 装饰器），定义在 `linhai/llm.py` 中。所有消息类都必须实现此协议。

```python
@runtime_checkable
class Message(Protocol):
    """消息协议，定义消息类的接口。"""

    def to_llm_message(self) -> LanguageModelMessage:
        """转换为LLM消息格式。"""
        raise NotImplementedError()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_llm_message()})"

    def to_json(self) -> str:
        """转换为JSON字符串。"""
        raise NotImplementedError()

    @classmethod
    def from_json(
        cls, json_str: str, group_chat: "linhai.group_chat.GroupChat"
    ) -> "Message":
        """从JSON字符串创建消息实例。"""
        raise NotImplementedError()
```

### LanguageModel 协议

`LanguageModel` 协议定义了语言模型的基本接口，包括流式生成回答和获取token限制的方法。

### Answer 协议

`Answer` 协议定义了 LLM 回答的接口，支持异步迭代获取 token、获取消息对象、获取推理消息、中断和截断等功能。

## 消息类

### SystemMessage

系统消息，用于表示系统角色消息。包含模板和当前时间，在转换为 LLM 消息时会替换模板中的 `{|TOOLS|}` 和 `{|CURRENT_TIME|}` 占位符。

### SubagentSystemMessage

SubAgent 系统消息，用于表示 SubAgent 的系统角色消息。与 `SystemMessage` 类似，但内容更简单。

### ChatMessage

聊天消息，用于表示用户或助理角色消息。不支持系统角色（系统角色应使用 `SystemMessage`）。在转换为 LLM 消息时，用户消息会被 `<user>` 标签包裹。

### ToolCallMessage

工具调用消息，用于表示助理调用工具的消息。包含工具名称、参数和 `assert_success` 标志。

### RuntimeMessage

运行时消息，用于表示运行时产生的消息（如错误、警告、信息等）。通常在 `linhai/agent/base.py` 中定义。

### ToolResultMessage 和 ToolErrorMessage

工具结果消息和工具错误消息，用于表示工具调用的结果或错误。通常在 `linhai/agent/base.py` 中定义。

## 消息传递与处理

### AgentMessage

`AgentMessage` 类（定义在 `linhai/agent/message.py`）负责管理 Agent 的消息队列和相关操作，包括：

- 添加、删除、过滤消息
- 标记垃圾消息
- 处理排队消息
- 保存对话历史
- 添加软限制通知

### 消息转换流程

1. 各种消息类实现 `Message` 协议，提供 `to_llm_message()` 方法将消息转换为 LLM 可以理解的格式（通常是字典，包含 `role` 和 `content` 等字段）。
2. `AgentMessage` 维护消息列表，并提供给 `LanguageModel` 生成回答。
3. LLM 的回答通过 `Answer` 协议流式返回，包含普通内容和推理内容。
4. 回答结束后，`ChatMessage` 被添加到消息列表中。

## 消息缓存与序列化

所有消息类都支持 JSON 序列化和反序列化，通过 `to_json()` 和 `from_json()` 方法实现。这允许对话历史被保存到文件并在需要时恢复。

## 消息过滤与查找

通过 `filter` 列表可以找到特定类型的消息，例如：

- 通过 `isinstance(msg, ChatMessage) and msg.role == 'user'` 找到所有用户消息
- 通过 `isinstance(msg, RuntimeMessage)` 找到所有运行时消息

## 动态调整内容

消息对象可以动态调整自身的内容，但这可能会导致缓存失效。例如，`SystemMessage` 在转换为 LLM 消息时会根据当前工具列表动态生成系统提示。

## 总结

LinHai 的消息架构设计灵活且可扩展，支持多种消息类型和协议，能够满足复杂的对话和工具调用场景。通过统一的 `Message` 协议，不同种类的消息可以无缝集成到消息历史中，并正确转换为 LLM 所需的格式。
