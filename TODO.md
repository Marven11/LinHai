# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [x] 在SubAgent._execute_tool_calls执行工具失败的时候弹一条UI消息到SubAgent Tab
  - 你可能需要修改当前架构，让TUI支持接受对应消息
  - 消息样式和Agent Tab相同
- [x] 让compress_history_range在启动时显示一个ui_log，报告当前共有几条消息
- [x] 重构CLI的底栏
  - 应该抽象为一个Widget自己刷新自己
  - 这个Widget每0.5秒刷新一次，自动获取当前的message量
  - 每个Answer的token用量等信息由CLIApp传给这个Widget
- [x] 给一个配置让CLI底栏使用nerd font中的icon
  - 默认关闭，用户可以通过`[cli]`中的配置项打开
  - https://www.nerdfonts.com/cheat-sheet
    - 图标\uf49b代表缓存
    - 图标\uf27a代表消息
    - 图标\uf063代表in
    - 图标\uf062代表out
- [x] 限制subagent可以提出的clarifier数量
  - 默认每个subagent最多提出两个
- [x] 删除没被使用的exception

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 在解析工具调用出现JSON解析错误时，根据错误找到错误点附近的内容并返回给Agent
- [ ] 添加更广泛的测试，通过检查messages/message_processor属性检查Agent/SubAgent是否可以看到工具定义的System Prompt
  - 直接检测其中是否有相关工具的名字即可，不用太复杂
- [ ] 支持配置每类subagent的开关
- [ ] 有时agent会误用`json`而非`json toolcall`的代码块调用，写一个插件在此时警告Agent
  - 检测`json`代码块，看看是否可以获得正确的工具调用
  - 如果agent确实将工具调用放在json而非json toolcall中，警告：
    - 警告内容包括工具的名字，不包括工具的参数（太长了）
    - 弹一条UI消息
  - 你需要修改extract_tool_calls_with_errors添加参数，以重用代码
- [ ] 在“错误：有未解答的澄清问题，禁止使用”后面加上澄清问题的ID和内容，避免agent手动调用工具，产生多余工具调用
- [ ] 在“与已调用的工具存在冲突，已阻止调用”加上是和什么工具冲突
- [ ] OpenAiAnswer的estimated_usage会在哪里被用到？没有用则删除
- [ ] 修改GitDiffReviewPlugin
  - 如果Agent没有使用修改文件相关的工具则不启动subagent检查（因为git修改不是agent产生的）
    - 记得弹一条UI消息
- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
