# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [ ] 完成todolist系统
  - todolist定义
    - 多条agent需要完成的任务，由git diff reviewer审查
    - 每一条是一小段话，带有对应的ID
      - ID由generate_id生成
    - 格式为
      - `{todolist_id}: {todolist_content}`
  - 类: TodolistManager
    - 完成todolist的管理功能
      - 添加todolist, 返回id
      - 列出todolist
      - 根据id删除todolist
    - 不需要持久化，每个manager在内存中独自管理各自的todolist
    - 实现agent, subagent的工具和CLI需要调用的函数
  - agent: 只能查看和添加todolist
  - subagent:
    - 需要修改prompt允许subagent调用多个工具
    - 可以查看、添加、删除todolist
    - 在审查git时额外获得todolist的内容
    - 并在prompt中被提示需要同时审查todolist的功能是否已经完成
    - 如果完成了则删除对应的todolist
  - 用户可以使用以下命令
    - /todolist_list 在CLI中列出todolist
      - 弹出一个widget展示todolist, 样式和其他message类似
        - 使用CSS绘制: 直角方形边框，适当的颜色，标题，
    - /todolist_add 添加todolist
      - 执行要弹出一条CliRuntimeNotice提示添加成功
    - /todolist_delete
      - 执行要弹出一条CliRuntimeNotice提示删除成功
    - 以上用户消息需要在linhai/cli层捕获，不能发送到对应的queue让agent获取！
  - 你很可能需要重构当前的命令系统，以支持这类不会被发送给agent的命令
    - 不要在CLIApp类中编写上述三个命令的实现，很不优雅
- [ ] 顺便重构CSS，将各个组件的CSS放在组件自己的class定义中，而不是全部放在CLIApp中
- [ ] 修改subagent的prompt, 让其在审查git时获得agent的回复后继续根据agent的回答进行追问
- [ ] 修改git diff reviewer, 让其在审查时同时获得agent回复自己的clarification
  - 需要改成在git diff reviewer中定义request clarification工具以实现捕获回复的功能
- [ ] 修改git diff reviewer, 让其审查不必要的函数副作用
- [ ] 修改prompt.py，增加和clarification相关的ACTION RULE
  - 强调clarification只有在问题完全解决之后才能回答
- [ ] 新的clarification在两分钟内禁止回答
  - 如果agent在两分钟内回答，则返回禁止信息，并提示：
    - 你需要注意prompt中的要求，先完成相关任务，再回答
    - 如果确实要回答，就sleep两分钟
- [ ] 修复CLI功能
  - reasoning content无法点击展开，且折叠时样式不对
  - welcome相关的widget没有自动隐藏

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] 改进检测思考中的工具调用功能，只在思考了但是没有调用时提醒
  - 如果思考中的工具在实际输出中被调用则忽略（因为agent已经实际调用了，不需要提醒）
- [ ] 让NormalContentWidget在被stop后还没有实际内容时unmount自己
  - NormalContentWidget被stop后其再也不会接收到新内容，此时如果还是空的话可以直接从CLI中隐藏
- [ ] 调整clarification相关的prompt
  - 在agent接收到clarification时提醒“仔细思考问题是否合理、是否漏掉了某些信息”
- [ ] 添加假设颠覆法

