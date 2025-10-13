# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 修改linhai/tool/tools/http.py，让fetch_article删除URL过长的image元素
- [ ] 编写保存对话历史的功能，在.local/share/linhai目录创建文件夹history，并在里面保存对话历史
    - 你应该需要修改linhai/agent.py，在每次生成结束后保存历史
    - 你需要使用linhai/llm.py中Message protocol的to_json
    - [ ] 编写相应的unittest
- [ ] 运行所有unittest并修复

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）
- [ ] 研究subagent集成
