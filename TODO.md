# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 使用./hypothesis_falsification.txt找出unittest打印这么多垃圾消息的原因
    - BaseExceptionGroup: unhandled errors in a TaskGroup等
    - 你可以写入临时脚本并运行
- [x] 为什么linhai/config.toml文件会被创建？
    - 我们不应该在这里写入配置文件，使用./hypothesis_falsification.txt找出原因并修改代码
- [ ] 拆分create_agent函数，至少应该拆出这些部分
    - 创建llm实例
    - 创建AgentConfig
    - 创建ToolManager
    - 创建init message
    - [ ] 修改实现，保证最小原则：每个分函数不应该接受整个config，而是只接受llm config等其需要读取的部分
    - [ ] 补充输入参数的type hint
- [ ] 修改agent的实现，如果用户的消息以`/queue`开头则不打断agent输出
    - 当前用户的输入总是打断agent输出
    - 编写unittest: 消息以/queue开头时不会被打断，否则被打断
- [ ] 修改/queue的实现：收到的/queue消息放在agent输出后面
    - [ ] 编写对应的unittest
- [ ] 在完成上一个commit之后我们发现已经有`@`系统和`/`命令系统了，我们需要一个统一的解析用户输入的方式
    - 在单独的文件中编写一个函数用来解析用户的输入，返回这个pydantic model
        - switch_model: 用户要求应该切换到哪个llm
        - command: 命令的名称，不包含`/`
        - mentioned: 不处于开头的`@`提到的名称，不包含`@`
    - 添加对应的unittest测试
    - 使用这个函数解析用户给agent的消息
- [ ] 在agent.py中添加一个工具`delete_message_by_uuid`，允许agent在运行时删除某个较大的工具结果消息
    - 当一个工具返回的内容大于30000字符时
        - 在agent对象的一个字典中记录
            - 字典为dict[uuid, 消息的引用]
                - 这里必须为消息的引用，不能是消息的索引，索引会因为历史压缩等原因变化
            - 每个较大的工具消息都有一个独立的uuid
        - 为agent提供一个runtime消息，告诉agent可以通过delete_message_by_uuid删除这个工具结果消息
    - 当token限制达到软阈值时：
        - 告诉agent优先通过在工作时顺手调用delete_message_by_uuid删除不需要的大块消息
            - 强调delete_message_by_uuid不会和其他工具发生冲突，可以同时调用
    - 编写unittest
        - [ ] 验证消息确实从self.messages中删除
        - [ ] 删除不存在的消息
        - [ ] 进行历史压缩，原消息被删除，索引发生变化之后再删除消息
- [ ] 添加显示当前token限制百分比的功能
    - 设计意图：展示当前消息长度距离模型token限制有多少，当前只有显示token用量的功能
        - 当前消息的token用量可以通过Answer类获得
    - [ ] 在配置中配置各个LLM的token上限（可选）
        - 这个上限和压缩token的限制不同（比压缩token限制小），放在各个llm的配置中
    - [ ] 给Agent类加一个函数，返回当前llm的名字和llm实例
    - [ ] 给LLM加上一个函数，返回当前的token限制
    - [ ] cli_ui在每次生成结束后，根据group chat获得agent，根据agent获得llm的名字（和配置中的llm.name一致）和llm的限制，计算出当前距离上限的百分比
    - [ ] cli_ui将当前token距离上限显示在token总用量旁边

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
