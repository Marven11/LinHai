# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 修复失败的MCP unittest: 严格按照./hypothesis_falsification.txt找出失败原因并修复
    - 参考 https://modelcontextprotocol.io/docs/develop/build-server 编写MCP服务器测试
    - 禁止跳过unittest！每个功能都必须获得良好的测试！
- [ ] 去除运行unittest时的垃圾消息: 严格按照./hypothesis_falsification.txt找出原因并修复
    - Before message generation callback error: Callback failed等
- [ ] 修复所有unittest
- [ ] 修复所有pylint+pyright报警

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
