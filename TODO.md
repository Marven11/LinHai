# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 重构AgentMessage，分离基础的消息管理(AgentMessage)和消息编排(AgentMessageOrchestration)
  - 基础消息管理包括管理基础的messages列表和appending messages集合，处理queue消息等
    - 也负责感知什么时候消息缓存失效
    - 基础消息管理不管理什么是大消息，什么消息应该删除，也不会引导agent执行消息管理相关的行为
  - 消息编排包括管理大消息、引导agent删除一系列消息或执行其他管理消息的行为
    - 包括各种消息管理工具的实现
    - AgentMessageOrchestration需要可以自定义CLI底栏显示的“当前有多少消息”的文本，而不是由CLI负责计算
      - CLI底栏可以分为多个piece，需要让AgentMessageOrchestration自己计算自己的piece
  - 同时需要将其他地方包含消息编排的实现全部移动到AgentMessageOrchestration中
  - 记得运行linhai测试

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] 在appending message中提供agent最近的思考内容
  - 需要解决的问题
    - agent每次生成消息都需要重新思考，生成reasoning content, 而在agent思考结束后
  - 当前的appending message只支持RuntimeMessage，需要修改为支持任意类型的Message
    - 需要检查传入的消息是否符合Message Protocol
    - 不支持
  - 创建新的Message: PreviousReasoningMessage
    - 根据agent的message processor找到最近的agent的消息（最多三条），提取其中的reasoning content
      - 注意需要在to_llm_message中动态获得agent的消息
    - 格式为
      - `<<previous_reasoning>><<message>>这是你之前的思考内容，仅做参考<<message>><<content>>xxx<<content>><<content>>xxx<<content>><<content>>xxx<<content>><<previous_reasoning>>`
  - 在模型支持思考时将PreviousReasoningMessage插入到appending message，否则移除
    - 通过在after message generation后检测reasoning content是否为None实现
- [ ] terminal tab和usage tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
