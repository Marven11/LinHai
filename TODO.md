# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 在linhai/llm.py中记录输入/输出token使用量
    - [x] 如果可以的话每生成一个token更新一次
    - [x] 同时编写getter函数，不支持记录token使用量的返回None
    - [x] 编写unittest并运行
- [x] 在CLI的输入框下面显示当前的输入/输出token使用量
    - 让CLIApp类读取Answer并显示输入/输出token使用量

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
