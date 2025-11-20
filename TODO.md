# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

- [ ] 将subagent的消息放在TUI中的新tab中，同时删除笔记tab
    - 需要调整subagent发送answer的方式和显示消息的样式和agent一致
    - [ ] 运行所有unittest保证没有破坏性修改
    - [ ] 测试：启动linhai，按下两次tab选择tab栏，然后按左右按键切换tab
- [ ] 删除ThinkingToolCallPlugin

注意：一定记得参考历史commit|git commit|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，必须创建terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 添加假设颠覆法
