# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 迁移到uv
    - [ ] 删除setuptools相关文件
    - [ ] 保证uv run python -m linhai可以正常使用linhai
    - [ ] 同步修改PROJECT.md和./LINHAI.md
    - [ ] 同步修改flake.nix保证nix build可以正常工作
- [ ] 在完成上一个commit之后我们发现已经有`@`系统和`/`命令系统了，我们需要一个统一的解析用户输入的方式
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
