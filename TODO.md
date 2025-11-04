# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 添加命令`/quit`和`/exit`，用户使用这个命令时退出
    - 你需要参考一下`/queue`的实现
- [ ] 你在e5c2b8cddbba584bda32a7703dd1934179d6fa65添加了assert_success参数但是没有在prompt.py中提及如何使用
    - 修改prompt.py
        - 介绍这个参数以及工具按顺序运行的逻辑
        - 修改示例，对“失败了也不会影响其他工具调用”的工具调用加上assert_success为False
- [ ] 简化617aa9a03b7b9029b6f5759ba0aebb3f156aa501中添加的有关self.compress_tool_called_in_last_response的逻辑
    - 在call_tool中设置self.compress_tool_called_in_last_response的值
    - 在state_working中读取
- [ ] 重构自动滚动
    - 当前cli_ui.py自动滚动（计算should_scroll）功能仅仅基于当前的屏幕滚动位置
    - 需要同时根据上一次用户滚动时间判断：如果用户上一次滚动在3秒内则不开启自动滚动
- [ ] 重构ID系统
    - 现在的terminal和agent.py中的大消息都使用uuid作为ID，重构
    - [ ] 在utils.py中写一个工具函数，生成这样的ID
        - `<prefix>_<bytes>`
        - prefix是`terminal`, `largemessage`这样的字符串
        - bytes是12位hex，如, 5486529a0022
    - [ ] 让terminal和大消息都使用这种ID
    - [ ] 编写unittest
    - [ ] 运行所有unittest
    - [ ] 在终端中启动`python -m linhai -m '@nothink 计算114+514并退出'`以测试有没有改坏
- [ ] 让终端工具支持ctrl+c等组合键的控制字符
    - 记得修改工具的描述：如果需要发送ctrl+c等对应的控制字符，请传入...
- [ ] 重构MessageWidget，让其在左上角显示当前llm的名字，而非assistant-reasoning等
    - 但是边框颜色还是根据role来计算
- [ ] 运行并修复所有unittest
- [ ] 运行并修复所有pylint/pyright警告

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
