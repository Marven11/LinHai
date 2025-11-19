# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 实现subagent系统
    - [x] 为subagent编写prompt到linhai/prompt.py
    - subagent设计
        - 每个subagent有对应的类型和名字，当前只有一个类型dummy用于测试
        - subagent启动时会获得一个消息，需要调用对应的工具完成对应任务并退出，退出时需要提供reason供agent检视
        - subagent不像agent一样可以响应用户消息，等待用户回答等，只会一直运行直到调用
            - subagent可以调用的工具和agent不同，目前只有sleep工具和exit工具
        - subagent的实现类似agent但是更加简单，完全没有用户交互的部分
    - 实现一个SubAgentManager用来管理所有sub agent的启动，关闭等
    - 实现对应的工具，让agent可以通过工具启动subagent并对话
        - create_subagent
        - check_subagent - 检查subagent的状态：是否运行，退出时留下了什么reason
    - 启动linhai测试：让linhai启动一个subagent，命令subagent睡眠5秒并退出

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，必须创建terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 添加假设颠覆法
