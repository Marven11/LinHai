# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 重构DuplicateFileReadPlugin, UnnecessarySedReadPlugin和UnnecessaryRunCommandPlugin的逻辑
  - 这是一个较为大型的重构，先输出markdown规划再修改
  - DuplicateFileReadPlugin: 仅检查read_file逻辑，完全删除检查read_file_with_sed的逻辑
  - UnnecessarySedReadPlugin: 在检测到读取“过小文件”或“已读取文件”时警告，超过3次才拦截，使用过read_file就重置计数
  - UnnecessaryRunCommandPlugin: 在检测到读取“过小文件”或“已读取文件”时警告，超过3次才拦截，使用过read_file就重置计数
    - 不区分是否是sed
    - 跳过用pipe连接起来的命令
    - 删除判断参数是否是文件路径的逻辑，仅通过检测“参数是否是存在的文件路径”判断参数是否是文件路径
  - 抽象检测“过小文件”和“已读取文件”的逻辑
    - “过小文件”: 字符数量少于15000且行数少于800行
    - “已读取文件”: 最新且和硬盘文件内容相同
      - 检查messages列表中的FileContentMessage，提取文件路径相同的FileContentMessage
      - 仅检查这些message中最新（列表相对位置更后）的message，其需要满足文件内容和硬盘文件内容相同
      - 检查这个unittest是否通过
        - 有一系列文件路径相同message，历史message和硬盘文件内容相同，最新message和硬盘文件内容不同 -> 不拦截
  - prompt: 基本不变

# 暂时搁置

- [ ] 我们需要重构解析agent回答的流程
  - agent的回答是一个token stream，我们需要从其中解析出三类token以传给cli显示
  - agent的输出包含reasoning_content和content两部分，我们需要解析为至少三部分
    - reasoning message - 只有一个
    - normal message - 可能有多个
    - toolcall message - 可能有多个
  - 同时我们需要在解析时为每一个message生成uuid以方便定位
  - 参考streamjson和linhai/cli/token_parser.py
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
- [ ] terminal tab
- [ ] 添加假设颠覆法
- [ ] asyncio.iscoroutinefunction将在python 3.16中被移除，需要改成inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动linhai时TUI焦点锁定在tab区域，需要按下tab键选择对话区域才能使用pageup/pagedown翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 
