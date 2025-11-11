# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 参考./ANALYSIS_AGENT.md重构linhai/agent/main.py
    - [x] 抽象message处理逻辑
        - 首先把处理messages的逻辑抽象为AgentMessage类，保存在message.py中，让agent通过合理的接口调用
        - 编写并运行unittest
        - 运行所有unittest以确认没有破坏性更改
    - [x] 抽象工具调用逻辑
        - 把处理工具调用的逻辑抽象为AgentToolcall类，保存在toolcall.py中，让agent通过合理的接口调用
        - 编写并运行unittest
        - 运行所有unittest以确认没有破坏性更改
    - [x] 抽象创建Agent逻辑
        - 将初始化agent等的逻辑都移动到create.py中
- [x] linhai/agent/workflow.py没有使用linhai/agent/message.py中定义的message处理方式，导致无法正确删除消息
    - [x] 先编写unittest测试workflow是否按照linhai/agent/main.py的方式正确处理message
        - [x] 这个unittest会失败，因为workflow.py没有正确删除消息
    - [x] 根据linhai/agent/main.py修改workflow.py
- [ ] compress_history_range会将一个True加入到消息中
    - 现在compress_history_range返回bool但是workflow的返回值会被直接加入到消息列表中
    - 应该修改compress_history_range的实现以及添加/修改对应的unittest，确保奇怪的True不会被加入
- [ ] 使用pyright扫描整个项目并修复
- [ ] 运行所有unittest并修复
- [ ] 消除unittest中的警告消息
    -  RuntimeWarning: coroutine 'TestAgentToolcall.test_call_tool_state_change' was never awaited等

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
