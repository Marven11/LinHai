# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 改进compress_history_range
    - [ ] 第一个小任务
        - 重构其的实现，将一部分代码拆到其他函数中，这个函数太长了
        - 运行所有unittest保证没有破坏性更改
    - [ ] 第二个小任务
        - 这个workflow会让agent生成一个包含被压缩信息的总结，以及一个json，包含被压缩信息的开始结束编号
        - 可是workflow会删除其注入的prompt但是不会删除agent生成的总结
        - 我们需要同时删除（pop）对应的总结，将总结的文本包裹一下插入到被删除消息的原位置上
            - 包裹一下是为了告诉agent这里的消息被删除了，并让agent在正确的位置读取总结
        - 需要编写unittest
    - [ ] 第三个小任务
        - 这个workflow在插入request之后会退出，但是有时会提前return导致request没有被删除
        - 可能用try catch来写比较好
        - 需要编写unittest
- 运行所有unittest保证没有破坏性更改

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
