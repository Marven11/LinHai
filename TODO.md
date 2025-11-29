# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [ ] OpenAiAnswer的estimated_usage会在哪里被用到？没有用则删除
- [ ] 在“错误：有未解答的澄清问题，禁止使用”后面加上澄清问题的ID和内容，避免agent手动调用工具，产生多余工具调用
- [ ] 在“与已调用的工具存在冲突，已阻止调用”加上是和什么工具冲突
- [ ] 有时agent会误用`json`而非`json toolcall`的代码块调用，写一个插件在此时警告Agent
  - 检测`json`代码块，看看是否可以获得正确的工具调用
  - 如果agent确实将工具调用放在json而非json toolcall中，警告：
    - 警告内容包括工具的名字，不包括工具的参数（太长了）
    - 弹一条UI消息
  - 你需要修改extract_tool_calls_with_errors添加参数，以重用代码
    - 让其支持自定义参数，默认json toolcall可以改成`json`
    - 然后在插件里使用这个参数检测json块
- [ ] 修复截断逻辑
  - 让插件在截断后不返回True，True代表打断agent

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加假设颠覆法

