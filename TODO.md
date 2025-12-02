# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] llm.py调用api失败时发送CliRuntimeNotice警告“网络失败”等，将要在约几秒后重试，让用户知道发生了什么
- [x] 添加插件拦截不必要的sed调用
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
- [x] subagent tab不显示subagent的思考内容
  - 需要重构subagent将token发送到cli的逻辑
    - 目前发送的token信息会不必要地转换成一个字典再发送，逻辑混乱，而且和agent发送token的逻辑不一致
    - 需要直接在queue中传输AnswerToken和Answer，参考agent消息的逻辑
      - 为了同时发送subagent名称和AnswerToken/Answer，你可以创建wrapper类
    - 因为我们在queue中传输数据，传输字典会丢失类型信息，不利于debug, 尽量使用自定义类(dataclass/pydantic)以减少心智负担
      - 顺便把上面这段话加入到group_chat.py中以便指导未来agent编写代码

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] terminal tab和usage tab
- [ ] 添加假设颠覆法

