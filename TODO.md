# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [x] 修改GitDiffReviewPlugin，如果这一次和上一次完全没有变化则不启动
  - 包括文件修改、新增文件的内容、删除文件的列表
  - 编写unittest

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 合并run_simple_command和run_complex_command，并且完全清理工具调用确认机制
  - 删除对应的配置项、代码、函数、测试
  - 我们的目标是让Linhai总是YOLO运行: You Only Look Once, 完全不需要用户确认工具调用
- [ ] 现在ReasoningContentWidget使用了错误的方法处理反转义，这个问题的原因是无论怎么escape都会导致rich库崩溃
  - 你需要让这个widget和其他widget一样使用Syntax渲染内容，在折叠时渲染为text，展开时将思考内容渲染为markdown
- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
