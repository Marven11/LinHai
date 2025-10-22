# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 为命令行添加-f选项，从文件中读取用户的初始prompt
    - [ ] 编写并修复对应的unittest
    - [ ] 尝试运行linhai测试这个选项，文件里写“调用工具退出...”，如果1分钟内没有及时退出则说明选项失败
- [ ] 将linhai/config.py中的config配置改成使用pydantic，并在linhai/agent.py创建agent时使用pydantic验证配置
    - [ ] 编写并修复对应的unittest
- [ ] 运行并修复unittest

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
