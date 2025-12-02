# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 修改linhai/subagent/types/git_diff_reviewer.py，新增的文件大小大于32KB时不要带上内容，只带上路径
- [ ] 当前使用`/todolist_add`并回车后消息仍然残留在输入框中
- [ ] 修改代码的同时查看并更新MESSAGE_DESIGN.md
- [ ] 删除ChatMessage并改为更具有指向性的UserMessage和AssistantMessage
  - 如果ChatMessage还用来表示除了用户消息和assistant消息之外的内容，则修改
  - 我发现deepseek, kimi等的官方文档都推荐在assistant消息中保留reasoning content
  - 但是当前的设计不允许这一点
  - 需要在AssistantMessage中暂时保存reasoning message以允许这一点
- [ ] 大改当前的Message架构，让各个Message而不仅仅是runtime都使用尖括号风格的marker
  - 现在大部分消息都使用role=user且没有name标注
  - 需要为消息包裹上合适的marker，使用合适的name
  - 当前只有RuntimeMessage使用了marker，而且单个尖括号容易和XML数据混淆，需要改成双尖括号
  - 当前只有ToolResultMessage和ToolErrorMessage有合适的name标注
  - 需要修改对应的plugin
  - 需要为
  - marker设计
    - 使用双尖括号，如`<<runtime>>`，成对包裹内容，不使用xml风格的`/`表示结束
      - 如: `<<runtime>>这是测试消息<<runtime>>`
    - 最外层使用合适的marker标记message的种类
      - runtime使用`<<runtime>>`
      - tool使用`<<tool>>`
    - 中间使用合适的marker分隔各类信息，例如
      - GlobalMemory需要使用`<<filepath>>`标记路径
      - tool需要使用`<<message>>`标记消息, 使用`<<data>>`标记数据本身，使用`<<error>>`标记错误消息
  - 工具执行结果消息
    - 因为工具执行结果可能有各类不同的数据，需要仔细设计，包含以下数据
    - message: 工具执行结果的描述，人类可读，一般为简体中文
    - error: 仅在工具执行失败时有这个部分，人类可读，一般为简体中文
    - data: 工具输出本身
      - 要求raw bytes: 如果工具输出的是raw bytes则直接拼接，不允许通过JSON等转换
      - 执行命令工具、读取文件等有“多个输出”或有额外提示的工具
        - 可能有复杂的输出，包含return code, stdout, stderr等，当前是随意拼接进非结构化的字符串中
        - 此时需要让工具自己创建一个ToolResultMessage的子类，手动管理data部分的字符串
        - 需要在message中描述各个部分的意义，如return code代表什么
        - 如: `<<return_code>>0<<return_code>><<stdout>>xxxx<<stdout>><<stderr>>xxxx<<stderr>>`
        - 你可能需要让ToolResultMessage提供一个可以override的函数，方便子类自定义data部分的数据
- [ ] 貌似DestroyedRuntimeMessage没有被使用，确认并删除
- [ ] 修改AgentMessage，使其支持appending_messages
  - 当前的AgentMessage管理一个message列表，我希望支持“永远固定在末尾的消息”功能
  - 例如有这个列表: [M1, M2, M3, R1, R2]，其中R1和R2被“永远固定在末尾”
  - 我希望新消息到来时，插入在正常消息后，“永远固定在末尾”消息前
    - 也就是插入消息M4后变成[M1, M2, M3, M4, R1, R2]
  - 期望通过管理两个列表实现: message和appending_messages
  - 要求:
    - appending_messages目前只能插入RuntimeMessage
    - RuntimeMessage的来源不能重复
      - 你需要修改RuntimeMessage的定义，添加source属性保证这一点
      - source可以为None，表示“默认来源”，此时不能插入appending_messages
    - 重复则报RuntimeError
  - 期望appending_messages为一个set，在调用api时拼接在末尾
  - 编写完善的unittest测试行为
  - 让这些插件使用这个功能添加它们的runtime message:
    - BadMultiToolCall
    - ClarificationCheckPlugin
    - SingleToolCallReminderPlugin
    - OnlyReasoningPlugin
    - 当然记得在插件判断当前不需要提示时移除对应的runtime message
    - 你可能需要通过设计一个update appending message函数优雅地实现这个功能
      - 接收一个runtime message，替换或添加当前的消息
      - 接收的runtime message可为None，表示移除，没有对应消息需要移除时则不做任何行为
- [ ] 添加一个插件：如果agent重复读取同一个文件而且文件内容完全相同，则拦截
  - 你需要为read_file添加一个专门的Message: FileContentMessage
    - 包含文件路径和文件内容，可以比较
  - 通过查看agent的message是否有相同的FileContentMessage实现
  - 可能需要修改当前的lifecycle架构，期望修改AfterToolCallCallback的定义

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] terminal tab和usage tab
- [ ] llm.py调用api失败时发送CliRuntimeNotice警告“网络失败”等，将要在约几秒后重试，让用户知道发生了什么
- [ ] 添加插件拦截不必要的sed调用
  - 有时模型会分多次读取一个不大的文件，每次只读取几十行，这非常没有必要，需要在模型这么做时阻止模型并让模型读取整个文件
  - 判断规则 - 在一分钟内出现两次读取同一个文件的工具调用：
    - 对应文件行数少于1600行
    - 使用run_sed_expression
    - 工具返回结果小于10000个字符
  - 提示：
    - `错误：一分钟内多次小块读取代码文件`
    - `违反：优先使用read_file的要求`
    - `后果：难以理解文件内容、生成多条消息导致重复计费`
    - `为什么无法省下token: 1. 最终还是需要读取所有文件内容 2. 多次发送回答会导致多次计费token`
    - `为什么不能提升认知：文件不完整会带来认知负担、遗漏内容导致行为出错`
    - `建议：优先带上行号读取整个文件！如果必须只读取对应行号则先sleep一分钟！`
- [ ] 添加假设颠覆法

