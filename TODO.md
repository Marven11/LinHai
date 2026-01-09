# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 修复上一个commit c92ff243导致的类型标注问题，直接使用`type: ignore`因为这些问题不是我们造成的
- [ ] 改进minimax兼容性
  - minimax在使用stream=True时不会返回usage信息，这导致minimax不能兼容上下文管理功能
  - 需要在使用minimax（compatibility=minimax）时使用完全不同的调用API的逻辑
    - 传入stream=False
    - 假装我们在流式获取Token
    - 在拿到完整的回答后发送两个"Token"
      - 一个token包含所有reasoning content, 且content设置为None
      - 另一个token包含所有content，且reasoning content设置为None
      - 这之后提取完整回答的usage并单独发送
    - 也就是说我们伪造这样的“流式Token”
      - LLM生成了一个超长的token，包含所有思考内容
      - 然后又生成了一个超长的token，包含所有正常内容
    - 如果这个方案不行则继续切分这两个“超大Token”，按照行切分
    - 必须添加对应的函数并在函数注释中说明这一点
  - 在使用minimax时提示用户“minimax的api在开启stream时不返回usage，导致兼容问题，已关闭stream”

# 暂时搁置

- [ ] 我们需要重构解析agent回答的流程
  - agent的回答是一个token stream，我们需要从其中解析出三类token以传给cli显示
  - agent的输出包含reasoning_content和content两部分，我们需要解析为至少三部分
    - reasoning message - 只有一个
    - normal message - 可能有多个
    - toolcall message - 可能有多个
  - 同时我们需要在解析时为每一个message生成uuid以方便定位
  - 参考streamjson和linhai/cli/token_parser.py
- [ ] 重构工具返回格式，使其直接包含工具名而不是拆分成两个消息
- [ ] 让拦截secret内容的插件返回所有包含的secret名，而不是仅返回一个
- [ ] 重构工具调用结果的回调函数，仅提供一个工具调用结果的回调而不是分成多个
  - 直接在调用回调函数时提供工具调用的状态：成功、失败、被跳过
- [ ] 添加插件检查代码中的注释，在使用write_file等工具写入文件时使用正则提取其中可能的注释
  - 也许可以通过LSP实现？
  - 需要通过文件名判断检查什么类型的注释
  - 质问“这些是注释吗？如果是的话为什么要添加这些注释？这些注释是你加的吗？这是否符合用户的需求？”
  - 使用正则是合理的，因为为每个语言配置一个解析器过于复杂，而且添加的内容也不一定符合代码语法（多行字符串内容等）
  - 对于python: 不检测多行字符串
- [ ] terminal tab
- [ ] 添加一个列出所有terminal的函数
- [ ] 分离打断时发送给agent的文本和发送给UI的文本
  - 当前打断时会将本来应该发送给agent的文本也发送到UI中，如“不要模仿...”，我们不应该这么惊吓用户
- [ ] 添加假设颠覆法
  - 添加prompt到system message
  - 添加插件在输出对应标题前禁止调用工具，参考已有插件实现
    - 检测方法为检查```json toolcall前是否有对应的标题行
      - 如果没有任何一个对应的标题行但是有```json toolcall则打断
- [ ] asyncio.iscoroutinefunction将在python 3.16中被移除，需要改成inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动linhai时TUI焦点锁定在tab区域，需要按下tab键选择对话区域才能使用pageup/pagedown翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 
