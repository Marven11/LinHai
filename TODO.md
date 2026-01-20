# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] trojan.py不支持process_*系列工具，需要修改并测试
  - 根据SshMachineControl编写，确认可以对接
  - 需要分别为SshMachineControl和trojan.py编写测试，确认它们可以正常构造、发送、接收、解析所有process_*工具的请求响应
    - 这意味着需要为每个process_*工具，为SshMachineControl和trojan.py，为构造、发送、接收、解析分别编写unittest，总量为`2*2*4`个新unittest
- [ ] 让find_most_similar_in_files使用`<<>>`组织内容
  - 问题：当前格式使用repr，导致文件内容字符串被转义
  - 解决方案：仿照其他使用`<<>>`组织内容的地方，用`<<alternative>>`包裹每个可能的匹配
- [ ] WaitingUserPlugin没有在警告agent同时提示用户“已警告”，需要修改
- [ ] 在提示红绿灯状态时提示agent当前的缓存比例
  - 在prompt中修改上下文管理的prompt，删除“避免使用清理工具”的笼统要求，添加“清理工具会破坏缓存，你需要控制缓存比例在90%以上”的要求

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
- [ ] 启动时塞一条runtime message，告知“当前时间为...初始pwd为...” 防止agent不知道当前时间，防止切换目录后忘记当前目录
- [ ] 改进OnlyReasoningPlugin的RuntimeMessage
  - 当前的消息内容太吓人了
  - 改进：`检测到在思考后没有输出任何内容而是在</think>标签前就输出了工具调用等，应该在</think>标签后输出实际内容`
- [ ] 用户用-f指定的文件没有使用FileContentMessage，应该改正
  - 每当用户用-f指定一个文件时仅仅放入FileContentMessage即可，不需要添加“用户用-f指定...”和“文件内容如下”这些提示
- [ ] 改进ToolCallInReasoningPlugin
  - 问题：agent有时会在思考中尝试调用一些工具，但是在实际输出时忘掉或者认为自己“已经调用”
  - 当前仅在agent输出中完全没有调用思考时提到的工具时提示，这不合理
  - 目标设计：找出所有在思考消息中使用json toolcall调用但是没有在实际输出中调用的工具调用
    - 在判断“工具是否被调用”时，我们只检查工具名，即使此时工具参数不同也视为同类调用。
- [ ] 查看tiktoken的文档，改进当前检查工具输出长度的逻辑和配置，使用tiktoken检查工具输出的token数量
- [ ] process_create的默认等待时间由1秒改为30秒，并更新描述为“最多等待时间”

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
