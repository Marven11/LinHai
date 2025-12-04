# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] Context tab - 一个新的Tab，展示当前消息的情况
  - 在tab的中间展示当前有多少消息，各个类型的消息有多少，平均长度（字符数量）是多少，最长的消息是什么（支持折叠展开）
  - 展示当前的token用量，包含当前的输入token、输出token量以及缓存token的比例和量
  - 展示当前orchestration的状态，包含有哪些大消息，哪些被标记了，哪些没有被标记
  - 展示最近5条messages和所有的appending messages
  - 尽量使用合适的图表
    - 进度条表示百分比
    - 无序列表列出大消息，用合适的颜色标记展示哪些被标记为需要删除，哪些没有
    - 数据有合适的单位
    - 消息可能过长，不适合全部展示
      - 过长的消息一般使用reprlib加上省略号省略，上方的“最长消息”需要支持折叠展开 

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] 重构工具系统，支持current machine
  - 当前的run command read file等功能默认在本机上运行
  - 在连接到ssh之后支持通过switch machine修改这些工具的目标机器
  - 还需要提供一个list machines功能以实现管理已连接机器功能
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
