# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] 当前总是阻止agent重新读取文件，这不太合理
  - 改成如下机制：
    - 如果agent第一次重复读取文件则警告agent不要这么做并增加全局计数器
    - 第二次再次读取文件才阻止
    - 如果使用read_file正确读取了文件则清空全局计数器
      - 正确读取文件：指读取的文件内容和当前最新的不相同，或者文件没有读取过
- [ ] 当前init_message(s)的定义很混乱
  - 问题: agent和cli都使用了init_messages，但是都有各自的处理逻辑
  - 问题：有多处地方都构造了init_message，这不合理
  - 要求
    - 传入init_messages时去除init_messages的默认参数
    - init_messages的定义改为list[Message]，永远不为None
    - 每个使用init_messages的地方都要有合适的类型注释
    - cli显示init_messages时只提取UserMessage，忽略其他类型的Message
    - 应该只有_create_init_messages负责根据args创建逻辑，而不是从外部传入
- [ ] 更新MESSAGE_DESIGN.md
  - ToolResultMessage 和 ToolErrorMessage 已经被删除，需要更新
- [ ] 编写运行unittest
  - _create_init_messages可以创建对应message
  - -f和-m可以正常工作，最终创建的init message中有对应内容
  - ..

注意：不仅仅要完成这些任务的代码实现，还要完成unittest、代码质量检查等！

# 代码要求

本项目的大部分代码要求都在./CODE_REQUIREMENTS.md 中，探索代码架构时务必读取此文件！

如果你看不到此文件的内容，务必重新读取！

## 代码要求：unittest

这个项目的绝大部分 unittest 都是你写的，且无人监督你的 unittest 实现，你对 unittest 的所有错误行为负责

开发新功能时：必须添加新的 unittest

修改任何代码时：必须规划查找相应代码对应的 unittest 并修改

删除代码时：必须规划修改使用对应函数/常量/类的 unittest

unittest 失败时，必须分析

- unittest 是否过时
- unittest 是否传入了错误的数据类型
- unittest 是否和用户期望不同

【注意】unittest 不得与用户要求相冲突，如果用户要求和 unittest 不同，必须修改 unittest
【绝对注意】禁止使用 if, getattr, hasattr, isinstance 等结构检查数据是否来自 unittest
【绝对注意】禁止使用 if, getattr, hasattr, isinstance 等结构检查是否是 Mock 类型的数据

不要用 pyright 检查 unittest 的类型错误，unittest 的类型错误会在运行 unittest 时自然出现

# 暂时搁置

- [ ] 重构工具调用结果的回调函数，仅提供一个工具调用结果的回调而不是分成多个
  - 需要规划，统计当前插件等会如何使用这些回调，重构后应该将这个回调设计成什么样
  - 当前有多个关于工具调用的回调，这不合理
  - 需要重构，改为只提供一个回调on_tool_result，删除其他回调
  - 需要重构，让其他插件都只使用这一个回调
  - 直接在调用回调函数时提供工具调用的状态：成功、失败、被跳过
- [ ] 添加插件检查代码中的注释，在使用 write_file 等工具写入文件时使用正则提取其中可能的注释
  - 也许可以通过 LSP 实现？
  - 需要通过文件名判断检查什么类型的注释
  - 质问“这些是注释吗？如果是的话为什么要添加这些注释？这些注释是你加的吗？这是否符合用户的需求？”
  - 使用正则是合理的，因为为每个语言配置一个解析器过于复杂，而且添加的内容也不一定符合代码语法（多行字符串内容等）
  - 对于 python: 不检测多行字符串
- [ ] terminal tab
- [ ] 添加假设颠覆法
  - 添加 prompt 到 system message
  - 添加插件在输出对应标题前禁止调用工具，参考已有插件实现
    - 检测方法为检查```json toolcall 前是否有对应的标题行
      - 如果没有任何一个对应的标题行但是有```json toolcall 则打断
- [ ] conversation 系统
  - 为每次对话创建一个文件夹`~/.local/share/conversation`，注意没有 s
  - 将当前历史消息存放在 context.json 中
    - 可能需要重构当前保存读取消息的方法，以标记每个消息的类型，便于恢复
  - 将规划文件、被删除的消息、大消息等都放进这个文件夹
- [ ] 在配置中支持对机器设置命令白名单
  - 可能需要考虑如何实现检测通过终端执行的命令
- [ ] 查看tiktoken的文档，改进当前检查工具输出长度的逻辑和配置，使用tiktoken检查工具输出的token数量
- [ ] 当前拦截带有secret的返回值时会直接丢弃内容，这不合理
  - 需要修改逻辑，在拦截带有secret的工具输出时将原工具输出写入/tmp文件
  - 需要修改README介绍secret system的功能，并警告用户“这个功能仅用来防止隐私被泄漏给API提供商，且此功能会将带有secret的内容临时保存在/tmp文件以便agent后续处理”
- [ ] 添加初始化配置的功能

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
