# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 将linhai/llm.py中的AnswerToken改为使用pydantic
    - [ ] 检查是否有对应的unittest，如果没有则添加
- [ ] 运行并修复unittest
- [ ] 使用pyright检查并修复错误，消除pyright的警告
    - 避免使用注释supress错误和警告
- [ ] 再运行并修复unittest

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
