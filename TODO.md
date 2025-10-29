# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 我刚刚重构了代码，添加了对MCP的支持，编写对应的unittest并运行
    - 你可能需要参考mcp_server_example.py
- [x] 对unittest运行pylint，修复错误和警告
- [ ] 运行并修复所有unittest
- [ ] 支持通过配置添加MCP，可以自定义MCP服务器的名字和路径
    - 路径是相对配置文件而非当前目录的，需要将相对路径根据配置文件路径转换成绝对路径
        - [ ] 编写这个细节的unittest
    - [ ] 编写完善的unittest
- [ ] 再次运行并修复所有unittest

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
