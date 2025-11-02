# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 改进CLI，在用户没有输入消息时在空白区域中央显示LOGO等欢迎消息
    - 用ASCII字符画展示LINHAI字样
    - 在旁边附上当前版本v0.1.0以及当前LLM名字
    - 运行linhai测试是否成功
- [ ] CLI: 添加一类消息: 运行时消息
    - 样式
        - 没有边框，背景相对用户消息的背景略黑
        - 内容为 `[I] <实际的消息>`
            - 其中I为INFO的首字母，WARNING类推
                - 方框和其中的内容字体颜色: `[I]`为灰色，`[W]`为黄色，类推
    - 输入方法
        - CLI添加一个queue: cli_runtime_output
            - 传递内容为一个pydantic数据
                - level: INFO, WARNING等字符串，标记literal以便类型检查
                - content: 实际的消息内容
        - tool manager在调用工具成功/失败后向这个queue发送消息
    - [ ] 编写unittest并运行
        - tool manager在运行成功后会向这个queue发送消息
    - [ ] 运行linhai并测试
- [ ] CLI: 用户输入消息后隐藏欢迎消息

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
