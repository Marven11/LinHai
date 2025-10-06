# 实现了 to_llm_message 的类

以下列出了所有实现了 to_llm_message 方法的类，包括文件路径和行号。标记为完成的类已经实现了 to_json 和 from_json 方法。

- [x] ./linhai/tool/main.py:45 - ToolResultMessage
- [x] ./linhai/tool/main.py:72 - ToolErrorMessage
- [x] ./linhai/llm.py:17 - SystemMessage
- [x] ./linhai/llm.py:32 - ChatMessage
- [x] ./linhai/llm.py:63 - ToolCallMessage
- [x] ./linhai/llm.py:109 - ToolConfirmationMessage
- [ ] ./linhai/llm.py:158 - AnswerToken (TypedDict, 无需序列化)
- [x] ./linhai/agent.py:63 - CheapLlmStatusMessage
- [x] ./linhai/agent_base.py:26 - CompressRangeRequest
- [x] ./linhai/agent_base.py:58 - RuntimeMessage
- [x] ./linhai/agent_base.py:82 - DestroyedRuntimeMessage
- [x] ./linhai/agent_base.py:104 - GlobalMemory

注意：AnswerToken 是 TypedDict，不是类，因此不需要实现序列化方法。所有其他类已经完成了 JSON 序列化方法的实现。