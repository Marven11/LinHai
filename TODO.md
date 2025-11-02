# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 为terminal工具编写unittest,如果已有则查看有什么需要添加的
- [ ] 添加新的terminal工具：上下滚动，支持向上滚动和向下滚动
    - [ ] 添加unittest
    - [ ] 启动linhai并测试使用
- [ ] 在uv中运行pylint, pyright并修复错误
    - 每修一个文件就运行unittest测试

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
