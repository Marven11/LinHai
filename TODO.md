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
- [x] 历史压缩功能，在scores数量严重少于消息数量时（80%以下）警告agent需要输出所有分数（包括分数低的！！！），提醒agent重新开始压缩流程
- [x] 历史压缩功能，在system prompt中写清楚只有所有列出的消息中分数低的消息才会被删除，所以务必输出分数低的消息（分数高的消息则无所谓）
- [x] 历史压缩功能：现在的历史压缩threashold太硬了，应该在配置中支持软压缩限制compress_threshold_soft和硬压缩限制compress_threshold_hard，软压缩限制达到之后提醒LLM应该开始压缩（每次generate_response都提醒，问题不大），硬压缩限制达到之后直接开启压缩流程
- [x] 全局记忆功能：修改prompt, 在用户要求“记住”的时候最好加入到全局记忆中
- [x] 廉价LLM功能：让廉价LLM不要修改文件，如果所有文件都读取完毕，且没有读取其他消息的必要，则调用工具切换到普通LLM
- [x] 廉价LLM功能：每次生成前都插入一条消息，提醒agent现在是廉价LLM还是普通LLM，然后删除切换LLM时的runtime message（因为不需要重复提醒）
- [x] LINHAI_WAITING_USER的检测会在输出历史压缩的时候仍然警告agent“既没有使用LINHAI_WAITING_USER又没有调用工具”，generate_response应该加上一个选项关闭警告功能（默认打开警告）
- [x] 给llm.py加上超时功能和失败重试功能
- [x] 修改prompt: 在切换到廉价LLM时，尽量限制步数，否则廉价LLM可能会尝试修改文件
- [x] 全局记忆: 如果文件被移动或临时删除则会直接导致程序崩溃
- [x] 仔细修复每个文件中的警告，包括pylint和mypy
- [x] 用black格式化


注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 添加微信公众号文章读取功能
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）