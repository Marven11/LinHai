# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 完全删除要求agent使用`- [ ]`标记进行任务规划的任何相关内容，并删除对应的unittest
    - 我们的目标是完全删除相关功能，完全不检查、要求、提示agent进行任务规划
    - 你需要一个个读取并修改`linhai/*.py`和`linhai/agent/*.py`
    - 运行所有unittest查看是否有过时的unittest没有删除，是否破坏了其他不相关的unittest
- [ ] 调整NormalContentWidget等的边框颜色，使其和nord主题更加搭配
    - [ ] agent思考使用secondary
    - [ ] agent回答使用primary
    - [ ] 工具调用使用调整后的紫色
    - [ ] 用户消息使用调整后的绿色
    - [ ] 运行linhai确认可以成功启动

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，必须创建terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
