# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 我们需要重构解析agent回答的流程
  - 这是一个“脱胎换骨”式的重构，务必详细思考，广泛调查，先输出设计到./PLAN.md中，然后暂停，我审核之后继续
  - 当前环境
    - agent的回答是一个token stream，我们需要从其中解析出三类token以传给cli显示
    - agent的输出包含reasoning_content和content两部分，我们需要解析为至少三部分
      - reasoning message - 只有一个
      - normal message - 可能有多个
      - toolcall message - 可能有多个
  - 当前设计
    - LLM生成Answer将每个AnswerToken发送给agent
    - generate_response获得Answer
      - `async for token in answer`遍历每个token，但是什么都不做，仅调用回调后发送给CLI
      - 在遍历完毕后将整个Answer发送给CLI，并return answer（但是这个return值不会被使用）
    - cli/app.py在接收到AnswerToken后会拿出content和is_reasoning并发送给MessageWidget
    - MessageWidget通过TokenParser将token分为三类token: reasoning, toolcall, normal并展示在界面中
  - 期望设计: 编写linhai/parsed_message.py
    - 首先，我们将LLM生成的回答分为从解析前和解析后两种角度看到
      - 解析前
        - LLM生成回答时，首先（可能）会输出一系列reasoning token，然后会输出一系列normal token
        - 每个token都是一小段字符串
      - 解析后
        - 我们将每个回答中连续一段同类token称为一个segment
        - 首先（可能）会输出一段reasoning segment，包含一系列reasoning token
        - 然后输出normal segment和toolcall segment
          - normal segment指的是在```json toolcall外的文本，这些文本是agent给用户的“回答”
          - toolcall segment指的是在```json toolcall内的文本，其中有一个工具调用的json
    - ParsedAnswer类
      - 表示一个解析后的回答
      - 由agent负责初始化，初始化接收agent传来的Answer
      - 初始化时启动task，遍历并解析Answer中的AnswerToken
      - 解析时
        - 维护current_segment和segment queue
          - current_segment: 当前正在生成的segment，默认为normal segment
          - segment queue
            - 直接使用asyncio.Queue而非使用group_chat，group_chat是给单例设计的，ParsedAnswer不是单例
            - 需要发送给CLI的所有segment，需要添加current_segment
            - cli拿到segment后会创建对应的widget，segment和widget应该一一对应
        - 调用lifecycle回调，初始化时应该接收lifecycle本身
        - 不直接处理被打断的情况
          - agent打断时调用Answer的interrupt函数，也不发送Answer到对应queue
          - Answer的interrupt函数停止发送AnswerToken
          - ParsedAnswer遇到stop iteration自然停止解析
      - 在解析结束时不发送Answer，直接结束函数，让task自然停止
      - 提供一个函数: wait_parsing，等待task结束并返回bool
        - 返回true表示正常结束
        - 结束时await task，因此向上传递task的exception
        - 如果结束时发现answer被interrupt，返回False
      - CLI可以通过遍历ParsedAnswer的queue得到所有segment
    - segment
      - 一个typeddict，包含segment_type, content, is_finished三个字段
      - 由ParsedAnswer动态修改
      - cli拿到segment后会创建对应的widget，segment和widget应该一一对应
    - linhai/agent/main.py的generate_response函数
      - 获得Answer后包装为ParsedAnswer
      - 将ParsedAnswer通过queue发送到"parsed_agent_answer" queue
        - 这意味着需要删除"agent_answer" queue
      - 将检查用户输入的逻辑移动到回调中
      - 使用wait_parsing等待，并在被interrupt时返回
      - 将无用的返回值直接改为return None
    - linhai/agent/main.py用户打断回调
      - 在每个token生成后检查是否有用户输入，如果有则打断
      - 注意维持打断方式和插件打断不同，打断没有CliRuntimeNotice，RuntimeMessage内容也不同
    - cli
      - app.py在拿到一个ParsedMessage后将其传给MessageWidget
      - MessageWidget遍历其中的每一个segment，将segment传给对应的widget
  - 编写新unittest测试
    - ParsedAnswer是否可以正确解析
  - 实现编写完成后
    - 运行所有unittest
  - 参考
    - 参考streamjson和linhai/cli/token_parser.py

# 暂时搁置

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
- [ ] 给工具调用添加on_machine参数，强行指定工具在哪台机器上使用
  - 考虑在连接机器后再添加system prompt
  - 可能还需要添加插件：如果连续3次使用同一个on_machine，且on_machine和当前machine相同则开始警告
- [ ] conversation系统
  - 为每次对话创建一个文件夹`~/.local/share/conversation`，注意没有s
  - 将当前历史消息存放在context.json中
    - 可能需要重构当前保存读取消息的方法，以标记每个消息的类型，便于恢复
  - 将规划文件、被删除的消息、大消息等都放进这个文件夹
- [ ] asyncio.iscoroutinefunction将在python 3.16中被移除，需要改成inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动linhai时TUI焦点锁定在tab区域，需要按下tab键选择对话区域才能使用pageup/pagedown翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 
