# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 我修改了用户初始消息的传递方式，查看当前commit和上一个commit的区别，研究我的实现，然后修复过时的unittest
- [x] 列出所有实现了to_llm_message的类（使用grep），这些类是实现了Message protocol的类，附带上文件路径和行号输出到ALL_MESSAGE_CLASS.md中
- [x] 为Message这个protocol实现to_json和from_json方法，支持保存为json字符串，或者从json字符串中读取
- [x] 为每个实现了Message Protocol的类实现to_json和from_json方法
    - 每修改一个类，就修改ALL_MESSAGE_CLASS.md标记为已经完成，并且增加对应的unittest
- [x] 运行所有unittest并修复错误的unittest

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
