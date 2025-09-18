# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 现在agent的工具调用格式依赖markdown的` ```json `进行标记，这和普通的json块标记冲突，改成使用` ```json toolcall` 进行标记，参考test.py和test.md
    - [x] 编写/更新对应的unittest
- [x] 运行并修复unittest
- [ ] 添加一个plugin，在agent输出过多`- [x]`时（超过10个）提醒agent注意prompt中的内容，在已完成内容过多时忽略输出已经完成的小任务
    - 具体提示参考prompt.py
    - 有了这个plugin就不需要在prompt中指导agent在已完成任务过多时删除了
- [ ] 根据新的tool call标记更新其他插件，如ToolCallCountPlugin
- [ ] 如prompt等地方并没有提示使用新的json toolcall标记，使用grep找出对应的地方并更新
    - [ ] 更新prompt
    - 注意不要更新compress range时输出的，包含start id和end id的格式
- [ ] 再次运行并修复unittest
- [ ] 仔细修复每个文件中的警告，包括pylint和mypy
- [ ] 用black格式化


注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 添加微信公众号文章读取功能
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）