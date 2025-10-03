# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] （做完这一步暂停）汇报当前prompt.py中有多少种情况是禁止执行多条命令的
- [x] 完全删除prompt.py中关于安全与非安全工具、非只读工具的描述
    - [x] 使用grep仔细检查！核对每个含有“安全”或“只读”的行！
- [x] 使用mypy, pylint, black检查以下文件
    - [x] main.py
    - [x] tool/main.py
    - [x] tool/base.py
    - [x] tool/tools/command.py

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）
