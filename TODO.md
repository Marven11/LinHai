# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 参考~/duckduckgo-mcp-server/src/duckduckgo_mcp_server/server.py在linhai/tool/tools/http.py实现一个搜索工具
- [ ] 将linhai/cli_ui.py中的append_content_lazy彻底删除，因为后面“只显示思考内容的最后5行”，我们不需要使用lazy的方式提升性能
    - 改成append_content
- [ ] 修改运行命令的工具，在描述处提醒agent当前系统是什么(win/mac/linux/...)，可以执行常见的shell命令，使用时不要损坏用户的电脑
- [ ] 在compress_threshold_soft触发的时候，用百分比提醒agent还有多少token触发compress_threshold_hard，也就是强制压缩
- [ ] 使用mypy, black和pylint检查你的代码

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）
- [ ] 研究subagent集成
