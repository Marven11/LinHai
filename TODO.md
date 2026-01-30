# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [x] 当前处理`/`和`@`的逻辑极为混乱，需要重构
  - 问题: linhai/cli和linhai/agent都处理了命令，且各个命令的实现散落在各处
  - 期望：将所有命令的实现移动到linhai/cli/command_handler.py中，并让linhai/agent统一处理命令和`@`，linhai/cli完全不处理命令，除了tab补全
  - 这是一个较为大型的重构，需要仔细规划
  - 统计当前linhai/cli/app.py支持什么`/`命令，linhai/cli/command_handler.py又支持什么
  - 删除handle_user_message，清理linhai/cli/app.py处理`/`命令的逻辑，让receive_one_user_message直接使用linhai/cli/command_handler.py
  - 将所有处理`/`和`@`的逻辑都移动到linhai/cli/command_handler.py中
  - 编写unittest测试所有`/`命令
- [x] 修复agent生成消息时如何处理接收到的用户消息
  - 当前问题：在agent生成token时如果接收到用户消息时不会响应用户输入的`/`命令等，既不会响应`/queue`又不会响应`@llm`等
  - 需要先添加测试
    - agent输出token时用户输入`/queue 等下需要实现` - 应该不打断而是添加到queued消息中
    - agent输出token时用户输入`@llm2 继续` - 应该切换到llm2
  - 需要参考当前解析用户输入的方式完整支持所有`/`命令和`@`
- [x] 运行所有unittest并修复，需要先确认unittest为什么失败：环境模拟不完整/unittest过时/实现错误

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

- [ ] terminal tab
- [ ] 添加假设颠覆法
  - 添加 prompt 到 system message
  - 添加插件在输出对应标题前禁止调用工具，参考已有插件实现
    - 检测方法为检查```json toolcall 前是否有对应的标题行
      - 如果没有任何一个对应的标题行但是有```json toolcall 则打断
- [ ] 添加一个llm manager
  - 当前问题: 
    - 配置使用什么llm完全由agent控制，agent不应该关心llm api返回什么错误
    - 但是llm api有时会返回429或者报告文本长度过长，我们希望在这个时候临时轮换llm，但是agent不应该实现这个逻辑
    - 而且当前Agent类需要管理当前使用什么llm，这不太合理
    - 而且各个subagent或者未来的parallel agent可能需要同时使用当前配置的llm
  - 设计一个LlmManager管理所有llm，而不是让agent获得一个llms列表
- [ ] 添加初始化配置的功能
- [ ] 分离plugin.py到一个文件夹中，同类的放在一起。需要重新运行unittest以确认没有破坏性更改
  - 一个个移动插件，以避免大量输出或错误输出
- [ ] 删除context_thanox工具，完全剥夺agent手动调用thanox的能力，因为agent可能会觉得这个工具是“更方便”的清理上下文的方式
- [ ] kimi k2.5 有时会使用`<|tool_calls_section_begin|><|tool_call_begin|>`这样的格式调用工具
  - 特征是`<|tool_calls_section_begin|><|tool_call_begin|>`出现在第一行且没有正常的json toolcall格式
  - 添加插件，当发现输出符合这个特征时提醒正确的工具调用格式
- [ ] 将conversation的目录从.local/share/conversation改成.local/share/linhai/conversation
  - 记得添加unittest

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
