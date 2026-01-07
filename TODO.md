# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 我们需要重构解析agent回答的流程
  - agent的回答是一个token stream，我们需要从其中解析出三类token以传给cli显示
  - agent的输出包含reasoning_content和content两部分，我们需要解析为至少三部分
    - reasoning message - 只有一个
    - normal message - 可能有多个
    - toolcall message - 可能有多个
  - 同时我们需要在解析时为每一个message生成uuid以方便定位
  - 参考streamjson和linhai/cli/token_parser.py

# 暂时搁置

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
 
