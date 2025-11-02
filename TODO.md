# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 使用./hypothesis_falsification.txt解决问题: 使用run_complex_command运行uv run python -m linhai会卡住
    - 初始假设: 运行时产生了没有被catch的Exception
    - 注意不要自己使用run_complex_command运行这个命令！否则你也会被卡！
- [ ] 使用终端执行`uv run python -m linhai`时会卡住：没有妥善处理进程树
    - 使用linhai/tool/tools/command.py类似的方式创建进程组并在退出终端的时候关闭
- [ ] 将CLI的运行时消息内容改成灰色

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
