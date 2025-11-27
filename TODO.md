# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [x] 重构PyteTerminal使其使用asyncio.Task在循环中动态读取并更新，避免在update函数中才读取所有内容喂给pyte
  - 我们已经使用asyncio事件循环回调机制动态读取终端输出
  - 移除了update方法，完全使用异步读取循环
  - 编写并通过了所有测试

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 修改GitDiffReviewPlugin，如果这一次和上一次完全没有变化则不启动
  - 包括文件修改、新增文件的内容、删除文件的列表
- [ ] 现在ReasoningContentWidget使用了错误的方法处理反转义，这个问题的原因是无论怎么escape都会导致rich库崩溃
  - 你需要让这个widget和其他widget一样使用Syntax渲染内容，在折叠时渲染为text，展开时将思考内容渲染为markdown
- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
