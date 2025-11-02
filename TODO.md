# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 参考./terminal_example.py添加终端控制工具组
    - 不要注册到global tools中而是新建一个toolset
    - 工具
        - [x] 新建终端，返回终端对应的uuid
        - [x] 发送按键到终端
            - 输入为按键的列表，不能是单个字符串
        - [x] 发送命令到终端
        - [x] 读取当前终端的屏幕
        - [x] 关闭终端
    - [x] 编写unittest并运行
    - [x] 运行linhai让linhai尝试使用终端打开vim写入文件
- [x] 使用./hypothesis_falsification.txt调查unittest的失败原因
    - 必须保证实现(不含unittest)的代码质量：
        - group chat的register member只能在__init__中调用，用于注册自己（self）
        - 不能重复调用register member，不能注册除了自己之外的任何对象，更不能try catch捕获重复注册/不存在时的runtime error!
        - 如果出现了runtime error，你不能try catch, 而是应该找出没有注册/重复注册的原因并修复!
- [x] 修复其他unittest
- [x] 使用./hypothesis_falsification.txt调查unittest出现垃圾消息的原因，并修复
    - `Executing <Task pending name='Task-340' coro=<TestLLM.test_openai_er`等
    - openai库写得很垃圾，阻塞了其他协程，暂时不处理
- [x] 修复pyright和pylint的警告等，然后重新运行unittest确认
- [x] 在完成上一个commit之后我们发现已经有`@`系统和`/`命令系统了，我们需要一个统一的解析用户输入的方式
    - 在单独的文件中编写一个函数用来解析用户的输入，返回这个pydantic model
        - switch_model: 用户要求应该切换到哪个llm
        - command: 命令的名称，不包含`/`
        - mentioned: 不处于开头的`@`提到的名称，不包含`@`
    - 添加对应的unittest测试
    - 使用这个函数解析用户给agent的消息
- [x] 在agent.py中添加一个工具`delete_message_by_uuid`，允许agent在运行时删除某个较大的工具结果消息
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
        - [x] 验证消息确实从self.messages中删除
        - [x] 删除不存在的消息
        - [x] 进行历史压缩，原消息被删除，索引发生变化之后再删除消息


注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
