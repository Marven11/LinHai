# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] 重构subagent
  - 现在git diff reviewer插件通过group chat获得subagent的配置，只检查自己是否被启用，非常奇怪
  - 只需要保证没有被启用时不注册git diff reviewer就行
  - 记得检查unittest
- [x] 添加--code-style选项
  - --code-style选项用来指定对应的code style markdown文件，包含一系列代码风格要求，内容参考当前项目的./CODE_REQUIREMENTS.md文件
  - 对agent消息的影响
    - 在agent启动时将对应的文件内容以message的形式插入
    - 你需要设计一个新的消息class
  - 对git diff reviewer的影响
    - 重构git diff reviewer，在没有指定这个选项时不启动subagent，并弹出CLI消息提示为什么不启动
    - 删除默认的代码规范要求
    - 你需要在linhai/main.py中将args注册到group chat中让git diff reviewer获取
- [x] 在CLI底栏消息数量旁边使用括号标明被标记为垃圾的消息数量
  - 样式`xxx msg (xx marked) | in .....`
  - 开启nerd fonts时使用图标\uea81代替单词marked

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
