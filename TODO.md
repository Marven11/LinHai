# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 修改CLI，在输入框中输入`@`和`/`时弹出补全功能，在文本框顶部显示候选列表，运行linhai验证
    - 候选列表
        - 列表没有边框
        - 列表底部最靠近文本框的地方为最有可能的候选项
        - 一开始选择的元素为最有可能的候选项，可以使用上下箭头切换
        - 按下tab或者回车选择
    - 你可能需要阅读parse_user_input的实现和使用例理解`@`和`/`的解析流程
    - 在终端中启动python -m linhai然后在输入框中输入@看看有没有补全
- [ ] 在使用了json toolcall这个code block但是里面的工具调用格式有误时，仔细检查并提示
    - code block是不是合法的json
    - code block是不是object
    - code block有没有name和arguments参数
- [ ] 切换llm之后的逻辑有问题
    - compress_threshold_soft = int(soft_config * token_limit) if isinstance
    - TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'
- [x] 运行所有unittest确认没有破坏性错误

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
