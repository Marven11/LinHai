# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] unittest会删除当前文件夹的LINHAI.md，使用./hypothesis_falsification.txt找出原因并修复
    - 随时可以用git restore恢复LINHAI.md
- [ ] 现在compress_threshold_soft/hard的值是在初始化时就确定的，需要改成根据当前llm动态计算
    - 具体来说，我们需要实现这个效果：对于不同的LLM根据配置动态计算要不要添加软阈值提示
    - 编写unittest，测试切换llm之后会不会出现新的软阈值提示
- [ ] 再次修复所有unittest
- [ ] 修复所有pylint+pyright报警

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
