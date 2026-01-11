# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] commit 53107284c32b10807dbb653bc7e807242247786d完成了其中的TODO，但是没有正确修改interrupt的定义，需要重构
  - 完全修改Agent.interrupt，定义两个参数
    - agent_message: 放进RuntimeMessage塞进agent essages processor中的消息
    - ui_notice: 放进CliRuntimeMessage中的消息
  - 重写每一个使用interrupt方法的地方
    - agent_message：以runtime向agent对话的视角写：如“你刚刚...，禁止。。。！”
    - ui_notice：以runtime向用户描述agent行为的视角写：如“Agent...，已阻止” / “Agent被用户打断”
  - 修改对应unittest适应新的定义
- [ ] commit 53107284c32b10807dbb653bc7e807242247786d完成了其中的TODO，但是忘记了同步修改subagent消息的更新逻辑
  - 必须完全按照agent接收显示消息的方式！禁止修改任何和subagent无关的代码
- [ ] unittest会在当前目录创建AGENT.md垃圾文件，找到原因并修改
- [ ] commit 53107284c32b10807dbb653bc7e807242247786d引入了set_parsed_answer这个setter，改为在__init__中接收
  - 禁止编写任何setter
  - 同步修改unittest
- [ ] 运行所有unittest确认所有需要修改的unittest都修改完毕

# 代码要求

本项目的大部分代码要求都在./CODE_REQUIREMENTS.md中，探索代码架构时务必读取此文件！

如果你看不到此文件的内容，务必重新读取！

## 代码要求：unittest

这个项目的绝大部分unittest都是你写的，且无人监督你的unittest实现，你对unittest的所有错误行为负责

开发新功能时：必须添加新的unittest

修改任何代码时：必须规划查找相应代码对应的unittest并修改

删除代码时：必须规划修改使用对应函数/常量/类的unittest

unittest失败时，必须分析

- unittest是否过时
- unittest是否传入了错误的数据类型
- unittest是否和用户期望不同

【注意】unittest不得与用户要求相冲突，如果用户要求和unittest不同，必须修改unittest
【绝对注意】禁止使用if, getattr, hasattr, isinstance等结构检查数据是否来自unittest
【绝对注意】禁止使用if, getattr, hasattr, isinstance等结构检查是否是Mock类型的数据

不要用pyright检查unittest的类型错误，unittest的类型错误会在运行unittest时自然出现

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
 
