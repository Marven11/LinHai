# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 现在基于plugin检查`#LINHAI_WAITING_USER`的功能是坏的，即使agent的输出既包含工具调用又使用了`#LINHAI_WAITING_USER`这个marker，agent也会停下来
    - 成因是检查这个marker的两个工具是分开的，但实际上应该合并为一个工具：所有检查都通过之后才能改变agent的state为waiting_user
- [x] 删除历史消息时删除了过程中的用户消息，但仍然保留开头的用户消息，导致agent忽略过程中的用户消息，从开头的用户消息开始回复
    - 可以在删除时在原位置加上一条runtime消息，内容为所有被删除的用户消息
    - 应该要修改unittest
- [ ] 修复所有unittest
- [ ] prompt中加入当前廉价LLM是否可用
    - 现在在廉价LLM不可用时，agent仍然会尝试使用廉价LLM
    - 建议在system prompt中加入廉价LLM的消息，和global memory一样用单独的message对象表示，而不是像当前时间一样再给system prompt加上替换字符串的marker
- [ ] 修改当前compress_history_range的逻辑，不固定禁止删除前3条消息，而是通过检查message对象的类来判断当前start_id是否正确
- [ ] 感觉使用`#LINHAI_WAITING_USER`标记的prompt可以再优化，应该明确*以每条消息为单位*调用工具或者等待用户，这样相关的prompt还可以再优化
    - 做完这个任务之后不要git commit，等我看看修改
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