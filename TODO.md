# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [ ] 在解析工具调用出现JSON解析错误时，根据错误找到错误点附近的内容并返回给Agent
  - 需要修改linhai/markdown_parser.py
- [ ] 添加更广泛的测试，通过检查messages/message_processor属性检查Agent/SubAgent是否可以看到工具定义的System Prompt
  - 直接检测其中是否有相关工具的名字即可，不用太复杂
- [ ] 支持配置每类subagent的开关
  - 你需要为subagent_config补充合适的类型注释，其必须为SubAgentConfig
- [ ] 修改GitDiffReviewPlugin
  - 如果Agent没有使用修改文件相关的工具则不启动subagent检查（因为git修改不是agent产生的）
    - 记得弹一条对应的UI消息提示用户


注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] OpenAiAnswer的estimated_usage会在哪里被用到？没有用则删除
- [ ] 在“错误：有未解答的澄清问题，禁止使用”后面加上澄清问题的ID和内容，避免agent手动调用工具，产生多余工具调用
- [ ] 在“与已调用的工具存在冲突，已阻止调用”加上是和什么工具冲突
- [ ] 有时agent会误用`json`而非`json toolcall`的代码块调用，写一个插件在此时警告Agent
  - 检测`json`代码块，看看是否可以获得正确的工具调用
  - 如果agent确实将工具调用放在json而非json toolcall中，警告：
    - 警告内容包括工具的名字，不包括工具的参数（太长了）
    - 弹一条UI消息
  - 你需要修改extract_tool_calls_with_errors添加参数，以重用代码
- [ ] 添加假设颠覆法

