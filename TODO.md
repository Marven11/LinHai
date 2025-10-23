# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 修改linhai/agent_plugin.py如果模型没有输出方框`- [ ]`或者`- [x]`则提醒模型需要进行任务规划
    - 建议使用正则匹配每一行开头的` *- \[[ x]\]`，没有则提醒使用`- [ ]`或者`- [x]`
    - 编写unittest
- [ ] 修改linhai/prompt.py中的示例，修改其中的任务规划格式为markdown分级无序列表+方框
- [ ] 运行并修复unittest
- [ ] 看一眼git stash，我刚刚在开发mcp client，帮我git stash pop

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
