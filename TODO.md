# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [ ] 合并run_simple_command和run_complex_command，并且完全清理工具调用确认机制
  - 删除对应的配置项、代码、函数、测试
  - 我们的目标是让Linhai总是YOLO运行: You Only Look Once, 完全不需要用户确认工具调用

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 现在ReasoningContentWidget使用了错误的方法处理反转义，这个问题的原因是无论怎么escape都会导致rich库崩溃
  - 你需要让这个widget和其他widget一样使用Syntax渲染内容，在折叠时渲染为text，展开时将思考内容渲染为markdown
- [ ] 修改架构，现在的Answer只能被打断生成，但是不能被截断
  - 我们需要添加一个架构让Answer支持截断，相当于提前帮LLM结束输出
  - 作用：有时候LLM会调用大量工具，但是我们希望让其在调用5个工具之后停下来，我们可以通过提前截断手动停下LLM输出
  - 和打断的区别：
    - 打断是暂停输出，本次输出失败，其中的工具调用等信息都不会被处理
    - 提前结束是暂停输出，流程继续，就像LLM正常停止输出一样
- [ ] 将send_string_to_terminal的with_enter改成必须参数
  - 记得同时修改unittest
- [ ] 修改“收到来自SubAgent的澄清问题...”为“收到来自SubAgent(@xxx)的澄清问题，ID为yyy....”，其中xxx是SubAgent的ID, yyy为澄清问题的ID
  - 让Agent明白SubAgent的ID是什么，澄清问题的ID又是什么
- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
