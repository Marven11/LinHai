# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 使用./hypothesis_falsification.txt解决问题: 使用run_complex_command运行uv run python -m linhai会卡住
    - 初始假设: 运行时产生了没有被catch的Exception
    - 注意不要自己使用run_complex_command运行这个命令！否则你也会被卡！
- [x] 使用终端执行`uv run python -m linhai`时会卡住：没有妥善处理进程树
    - 使用linhai/tool/tools/command.py类似的方式创建进程组并在退出终端的时候关闭
- [x] 将终端工具改成同步函数
    - PyteTerminal本身是同步的，管理的进程也是同步的，异步是多余的
    - ToolManager会在新线程里运行同步工具
- [x] 运行所有unittest并修复
- [ ] 参考WrongEndPlugin添加另一个插件：在agent生成消息时如果有一行内容有`<｜end▁of▁[a-z]+｜>`且前面都是汉字，则打断输出
- [ ] 让agent.py在generate response接受到/queue消息时将消息存入self中而非本地变量中，以防消息被打断时用户消息丢失
    - [ ] 编写unittest测试有/queue消息时，agent生成被打断会不会丢失用户消息
- [ ] 让agent.py在解析用户消息时使用input_parser.py
- [ ] 让agent.py生成消息被插件/用户打断的时候发送一条“Agent被XX打断”runtime message到cli_ui.py
- [ ] 将CLI的运行时消息内容改成灰色

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
