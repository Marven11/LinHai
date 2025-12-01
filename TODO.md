# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 改进检测思考中的工具调用功能，只在思考了但是没有调用时提醒
  - 如果思考中的工具在实际输出中被调用则忽略（因为agent已经实际调用了，不需要提醒）
- [ ] 让NormalContentWidget在被stop后还没有实际内容时unmount自己
  - NormalContentWidget被stop后其再也不会接收到新内容，此时如果还是空的话可以直接从CLI中隐藏
- [ ] 调整clarification相关的prompt
  - 在agent接收到clarification时提醒“仔细思考问题是否合理、是否漏掉了某些信息”
- [ ] 清理getattr使用
  - 在绝大多数时候我们都可以确定某个数据的类型，也就不需要getattr
  - 无法获知类型往往是因为类型注释有误，修复类型注释
  - 有时候unittest的错误会导致某个对象缺乏属性，此时修复unittest
  - 例外：暂时忽略openai库产生的数据，openai的异步API类型注释有问题，使用getattr是合适的
- [ ] 整理当前的message架构，输出到MESSAGE_DESIGN.md中
  - 大致是：
    - 现在每个message都是一个符合Message协议的对象，支持转为LlmMessage
    - LlmMessage就是调用api时放入messages数组的元素
  - 你需要描述Message的种类、Message如何传递
  - 重点是这样我们就可以细化每种message的种类，从而更加精细的调整
    - 可以通过filter列表来找到对应的message
    - message可以动态调整自身的内容（虽然这可能会导致缓存失效）
- [ ] 添加插件，检测deepseek是否只思考不输出，表现为只有reasoning content没有content
  - 检测是否只有reasoning content没有content即可！
- [ ] 当前reasoning content在不是current message时无法点击展开隐藏，修一下
  - 问题在于被stop后需要手动调用update_display
  - 需要注意性能问题：app.py调用stop表示没有新内容传入，此时widget必须关闭timer以避免性能开销
  - 顺便加一下“app.py调用stop表示没有新内容传入”的注释
- [ ] 修改插件，在llm为deepseek且正在模仿runtime时阻断输出
  - 特征为开头是`<runtime>`，且含有`</runtime>`
  - 以后还可以支持阻断工具输出，但是工具输出的格式还没有改成`<tool>`这样的格式，先加一个注释TODO提示一下
  - 目前只能通过compatibility判断是否是deepseek，需要用户手动配置，这是合理的
- [ ] 修一下reasoning content的样式，关闭wrap

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] 添加一个插件：如果agent重复读取同一个文件而且文件内容完全相同，则拦截
  - 你需要为read_file添加一个专门的Message: FileContentMessage
    - 包含文件路径和文件内容，可以比较
  - 通过查看agent的message是否有相同的FileContentMessage实现
  - 可能需要修改当前的lifecycle架构，期望修改AfterToolCallCallback的定义
- [ ] 添加假设颠覆法

