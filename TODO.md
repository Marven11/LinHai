# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 修改现在-f和-m选项的逻辑
    - 这两个选项可以同时使用且都可以指定多个，使用-f时像当前一样添加两个消息，使用-m添加一个消息
    - 例子: `-f ./README.md -f ./TODO.md -m '完成TODO'`一共是5条消息
        - `-f ./README.md`: 两条消息
        - `-f ./TODO.md`: 两条消息
        - `-m '完成TODO'`: 一条消息
    - [x] 编写对应unittest
- [x] 修改agent/main.py，在等待用户接收到用户的消息后直接转成working state
    - [x] 运行所有unittest并同步修改过时的unittest
- [x] 修改现在ToolResultMessage的逻辑，在消息过长时将消息分块保存到多个临时文件中
    - 如果消息长度大于1000行则每800行保存为一个文件，否则每10000字符保存为一个文件
        - 每800行而非1000行是因为工具调用可能会给内容带上更多内容
    - 记得返回是按行分割还是按字符分割，文件名带上行号或者字符号开始和结束
- [x] li_ui.py太长了，按照代码结构拆分到linhai/cli/文件夹中，然后修复uv run pyright linhai/ tests/的错误，最后运行unittest查看是否有破坏性更改
- [x] 修改append_file，默认检查目标文件是否以空行结尾，新的内容默认从新的一行开始
    - 添加一个assume_empty_line选项，默认为true
    - assume_empty_line为true时检查目标文件最后是否有换行符\n
    - assume_empty_line为false时直接拼接内容
        - 但如果新加的内容开头和原文件末尾都没有换行符号则返回警告：原文件末尾没有换行，原最后一行被修改！你最好重新读取一下这个文件
- [x] 修改prompt中关于绿灯和绿灯闪烁的描述：绿灯时可以顺手标记大消息，绿灯闪烁应该积极标记大消息
    - 记得同步修改add_soft_threshold_notification
- [ ] 运行所有unittest确认没有破坏性错误

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
