# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 修改linhai/tool/tools/http.py中的fetch_article工具，使其使用自定义filter在最终的markdown中使用html风格的表格，不使用markdown表格
    - 但是删除表格中所有元素的属性，在最终的markdown中不要包含表格元素的属性，以保证markdown可读且简单
- [x] 修改linhai/tool/tools/http.py中的fetch_article工具，使其删除URL过长（超过800字符）的image元素
- [x] 编写unittest并运行

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）
