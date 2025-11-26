# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行 git commit，消息参考历史

- [ ] 重构subagent
  - 根据subagent的type去获取prompt
  - 将SubAgentCollaborationPlugin的task_message移动到prompt.py中，并在使用时使用.format格式化
    - 这样SUBAGENT_CHECKLIST就不需要存在了，合并到task_message中并删除这个常量

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加一个subagent插件: git diff审查
  - 在agent使用#LINHAI_WAITING_USER时并且当前目录是git仓库时启动
  - 将当前的git diff保存成字符串并传给subagent
- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
