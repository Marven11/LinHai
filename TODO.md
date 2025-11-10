# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 参考./ANALYSIS_AGENT.md重构linhai/agent/main.py
    - 抽象message处理逻辑
        - 首先把处理messages的逻辑抽象为AgentMessage类，保存在message.py中，让agent通过合理的接口调用
        - 编写并运行unittest
        - 运行所有unittest以确认没有破坏性更改
    - 抽象工具调用逻辑
        - 把处理工具调用的逻辑抽象为AgentToolcall类，保存在toolcall.py中，让agent通过合理的接口调用
        - 编写并运行unittest
        - 运行所有unittest以确认没有破坏性更改
- [ ] 修改llm.py的重试逻辑，让其无限次重试
- [ ] 升级list_files，使其显示每个文件/文件夹的类型等，格式类似gnu的ls -lah
- [ ] 修改现在的软阈值消息提示：
    - 将现在的静态格式改成根据当前的比例分别提醒当前是处于绿灯、绿闪、黄灯还是红灯
    - 不重复提醒绿灯：如果当前绿灯的状态没有改变则不提醒，如果由其他状态转为绿灯则提醒

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
