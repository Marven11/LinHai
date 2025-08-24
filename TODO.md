# 等待执行

依次完成以下任务，逐个commit，消息参考历史，最后每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 实现临时切换到廉价LLM的功能
- [x] 临时切换到廉价LLM限制最多3个消息
- [x] 修改prompt，添加廉价LLM的内容，积极使用廉价LLM读取代码，但是不要使用廉价LLM编写代码（廉价LLM应该避免编写代码）
- [x] 修改agent.py，如果读取文件是没有使用廉价LLM，提醒agent
- [x] 修改prompt，在LLM压缩历史前使用廉价LLM
- [x] 修改廉价LLM启用功能，在没有廉价LLM时提醒LLM启用失败，而不是什么都不说
- [x] 修改prompt中的示例，在压缩历史时输出总结
- [x] 修改prompt, 在压缩历史时留下对文件修改的tool调用，并删除已经过时的文件内容（最好重新读取）
- [x] 尝试简化agent.py中的generate_response函数，将async for token in answer中的逻辑、根据self.cheap_llm_remaining_messages选择模型，以及修改self.cheap_llm_remaining_messages的模型移动到其他函数中
    - [x] 最好将获取llm的逻辑放在独立的函数中，然后将llm从self.config["xxx_model"]中移出，放到`self._xxx_model`中
- [x] ToolCallMessage中的argument没必要使用json dump
- [x] create_agent中skip_confirmation和whitelist没有使用
- [x] 仔细修复每个文件中的警告，包括pylint和mypy，然后用black格式化
- [ ] 历史压缩功能，在scores数量严重少于消息数量时（80%以下）警告agent需要输出所有分数（包括分数低的！！！），提醒agent重新开始压缩流程
- [ ] 历史压缩功能，在system prompt中写清楚只有所有列出的消息中分数低的消息才会被删除，所以务必输出分数低的消息（分数高的消息则无所谓）

注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 添加微信公众号文章读取功能
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）