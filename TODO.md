# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 在CLI中的welcome信息中修改当前的LLM提示和版本提示，添加动画
    - 首先显示每日一言，金黄色加粗，持续0.2秒
        - 当前的每日一言只有`/time set 0`，MC中设置时间的命令
    - 然后全部字符变成乱码，变成稍灰一点的黄色，持续1秒
        - 注意乱码字符的长度要长于每日一言和版本号信息
    - 最后变成当前版本号和LLM: 如`v0.0.1 | LLM: deepseek`，灰色加粗
    - 不要删掉彩虹色的标题！
- [x] 在CLI的底部状态栏Token左边添加当前LLM，类似`deepseek | in xxx | out xxx`
- [ ] 现在没有使用MCP就Ctrl+C退出会导致RuntimeError
    - 使用终端运行linhai确认行为
    - 在group_chat中添加函数，返回member是否存在
    - 在agent中使用这个函数，只有在mcp connector存在时才调用disconnect all
- [ ] 把使用CliRuntimeNotice发送Agent被插件打断的逻辑从generate_response移动到interrupt函数中，而且将消息的内容改为插件提供的custom message
- [ ] 修复所有unittest
- [ ] 修复所有pylint+pyright报警

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
