# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 我刚刚重构了代码，添加了对MCP的支持，编写对应的unittest并运行
    - 你可能需要参考mcp_server_example.py
- [x] 对unittest运行pylint，修复错误和警告
- [x] 运行并修复所有unittest
- [x] 支持通过配置添加MCP，可以自定义MCP服务器的名字和路径
    - 路径是相对配置文件而非当前目录的，需要将相对路径根据配置文件路径转换成绝对路径
        - [x] 编写这个细节的unittest
    - [x] 编写完善的unittest
- [ ] unittest会打印一些消息，使用./hypothesis_falsification.txt找出原因并清理
    - After message generation callback error: 'EmptyAnswer' object has no attribute 'get_reasoning_message'等
- [ ] 在create_agent函数中根据配置添加MCP
    - 组合优于继承，组合式优于选项式
        - 你应该将MCP connector的创建移动到create_agent函数中
        - 然后将创建的connector传给tool manager
- [ ] 再次运行并修复所有unittest
- [ ] 为什么linhai/config.toml文件会被创建？
    - 我们不应该在这里写入配置文件，使用./hypothesis_falsification.txt找出原因并修改代码
- [ ] 拆分create_agent函数，至少应该拆出这些部分
    - 创建llm实例
    - 创建AgentConfig
    - 创建ToolManager
    - 创建init message
- [ ] 修改agent的实现，如果用户的消息以`/queue`开头则不打断agent输出
    - 当前用户的输入总是打断agent输出
    - 编写unittest: 消息以/queue开头时不会被打断，否则被打断
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
        - 删除不存在的消息
        - 进行历史压缩，原消息被删除，索引发生变化之后再删除消息

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
