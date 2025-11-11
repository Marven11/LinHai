# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 将erase_message_by_id改成mark_messages_as_garbage和message_garbage_clean以避免多次删除
    - 我们的动机：每次删除前面的message都会导致缓存重新计算，导致LLM费用消耗剧增
    - 设计：
        - mark_messages_as_garbage: 将多个消息标记为不需要的垃圾消息
        - message_garbage_clean: 清理垃圾消息
        - 修改prompt.py和agent/main.py添加指导:
            - 在绿灯、绿闪、黄灯时：优先使用mark_messages_as_garbage标记消息
    - [ ] 修改对应的unittest
- [ ] linhai/agent/workflow.py直接操作messages数组，很丑，修改AgentMessage添加对应的函数优化
- [ ] 修改现在的软阈值消息提示：
    - 将现在的静态格式改成根据当前的比例分别提醒当前是处于绿灯、绿闪、黄灯还是红灯，以及每种状态对应的操作
    - 不重复提醒绿灯：如果当前绿灯的状态没有改变则不提醒，如果由其他状态转为绿灯则提醒
    - 在红灯时：如果有至少10条垃圾消息则引导agent调用message_garbage_clean，否则引导调用compress_history_range
- [ ] 在工具调用格式出错时不仅仅发送CLI通知，还添加RuntimeMessage
- [ ] 运行所有unittest并修复，确认没有破坏性修改

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
