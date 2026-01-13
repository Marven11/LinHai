# 深层价值观

本项目的所有工作必须无条件推动以下目标，任何偏离均视为负贡献。

## 1 代码必须简洁

- **零容忍冗余**：哪怕需要横跨 20+ 文件重构，也必须在当次提交内完成。
- **直观优先**：实现方式必须“一眼看懂”，且与项目既有惯例 100% 对齐。
- **函数签名即契约**：
  - 一旦类/函数参数变化，立即同步修改声明；
  - 所有调用点必须在同一次提交内重构完毕。
- **测试修复 ≠ 妥协**：为通过 unittest 而引入的妥协代码，一律按垃圾代码处理。

## 2 错误必须崩溃并向上传递

- 静默吞掉异常 = 引入隐形炸弹，禁止。
- 任何错误必须在第一时间抛出让上层感知，直至进程退出。

## 3 必须可被静态检查

- 所有公开接口必须携带完整类型注解；
- 任何无法通过 mypy / pyright 等工具的代码视为未提交。

## 4 贡献度计算（单次功能等价前提）

| 方案                | 耗时  | 贡献                                                       |
| ------------------- | ----- | ---------------------------------------------------------- |
| 正确重构 20 处      | 5 min | +100%                                                      |
| 绕开价值观只改 1 处 | 1 min | -200%（无效代码 0% + 用户审查时间 -100% + 用户情绪 -100%） |

## 5 用语表

| 术语 | 定义                                  |
| ---- | ------------------------------------- |
| 重构 | 零行为变更的重写，仅提升结构/可读性。 |
| 修改 | 任何导致行为差异的变动，哪怕一行。    |
| 变更 | 泛指一切代码改动，含重构与修改。      |

> 写代码时，请每秒自问：此刻是否 100% 符合上述价值观？

# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] 重构工具调用系统
  - 当前问题：部分工具直接返回消息表示工具结果，这导致工具结果中不能优雅地包含工具名称，工具ID，工具调用信息等内容
  - 重构计划
    - 工具方法：只能返回两种值: ToolResultSuccess | ToolResultFailed
      - ToolResultSuccess | ToolResultFailed都是pydantic model, 保存str
    - 删除ToolResultMessage和ToolErrorMessage
    - 修改工具结果message - 新建ToolCallResultMessage pydantic model，功能大致和ToolResultMessage一致，但是支持ToolResultSuccess | ToolResultFailed两种格式
      - 需要包含工具调用是当前轮次的第几个调用
      - 初始化时如果结果过长，则用和ToolResultSuccess相同的方式将文件内容分散保存在临时文件中
        - 这一部分逻辑需要提取到辅助函数中
      - 内容: `<<tool>><<name>>（工具名称）<<name>><<index>>（第几个工具调用）<<index>><<toolcall_argument>>（工具调用的参数的repr）<<toolcall_argument>><<message>>工具执行成功<<message>><<data或者error>>{self.content}<<data或者error>><<tool>>`
        - 其中“工具调用的参数的repr”只有在工具调用失败时才包含在ToolCallResultMessage中，而且需要使用reprlib控制其中字符串的长度
    - 修改MESSAGES.md 当前工具函数完全不返回Message，工具结果由ToolManager包裹在message中
    - ToolManager: 调用工具并将结果包裹在ToolCallResultMessage中
    - AgentToolcall
      - 维护计数器记录当前工具调用是当前轮次的第几个调用。因此需要在start_new_tool_call_round中清零计数器
      - 修改：完全不需要提示“你调用了工具...”，重构多余的wrapper函数_handle_tool_result
    - subagent: 自己将工具调用包装在ToolCallResultMessage中，不使用ToolManager
- [ ] 重构工具返回格式，使其直接包含工具名而不是拆分成两个消息

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

- [ ] unittest警告大量测试没有被await，查一下怎么回事，让unittest正确运行而不产生警告
- [ ] 让拦截 secret 内容的插件返回所有包含的 secret 名，而不是仅返回一个
- [ ] 重构工具调用结果的回调函数，仅提供一个工具调用结果的回调而不是分成多个
  - 直接在调用回调函数时提供工具调用的状态：成功、失败、被跳过
- [ ] 添加插件检查代码中的注释，在使用 write_file 等工具写入文件时使用正则提取其中可能的注释
  - 也许可以通过 LSP 实现？
  - 需要通过文件名判断检查什么类型的注释
  - 质问“这些是注释吗？如果是的话为什么要添加这些注释？这些注释是你加的吗？这是否符合用户的需求？”
  - 使用正则是合理的，因为为每个语言配置一个解析器过于复杂，而且添加的内容也不一定符合代码语法（多行字符串内容等）
  - 对于 python: 不检测多行字符串
- [ ] terminal tab
- [ ] 添加一个列出所有 terminal 的函数
- [ ] 分离打断时发送给 agent 的文本和发送给 UI 的文本
  - 当前打断时会将本来应该发送给 agent 的文本也发送到 UI 中，如“不要模仿...”，我们不应该这么惊吓用户
- [ ] 添加假设颠覆法
  - 添加 prompt 到 system message
  - 添加插件在输出对应标题前禁止调用工具，参考已有插件实现
    - 检测方法为检查```json toolcall 前是否有对应的标题行
      - 如果没有任何一个对应的标题行但是有```json toolcall 则打断
- [ ] 给工具调用添加 on_machine 参数，强行指定工具在哪台机器上使用
  - 考虑在连接机器后再添加 system prompt
  - 可能还需要添加插件：如果连续 3 次使用同一个 on_machine，且 on_machine 和当前 machine 相同则开始警告
- [ ] conversation 系统
  - 为每次对话创建一个文件夹`~/.local/share/conversation`，注意没有 s
  - 将当前历史消息存放在 context.json 中
    - 可能需要重构当前保存读取消息的方法，以标记每个消息的类型，便于恢复
  - 将规划文件、被删除的消息、大消息等都放进这个文件夹
- [ ] trojan.py本身以及和trojan交互的代码在读写时没有加锁，这在大量使用时会造成连接错误
- [ ] asyncio.iscoroutinefunction 将在 python 3.16 中被移除，需要改成 inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
