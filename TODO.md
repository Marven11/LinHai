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

- [ ] 添加初始化配置的功能
- [ ] 当前on_tool_result的命名不合适，改为after_toolcall
  - 需要同时处理类型名、函数名、变量名等
  - 需要搜索on_tool和ontool不区分大小写以查看是否还有遗漏，完成任务前必须确认没有遗漏
  - 需要保证unittest不失败，pyright linhai/没有错误
- [ ] 我们需要用更加简洁的设计复刻openclaw的核心功能
  - openclaw的核心功能：
    - 从各个IM接收用户消息并转发给agent, agent可以通过id等回应用户
    - agent可以暂停等待输入，但是暂停后每隔一段时间就会收到一条心跳消息而被打断暂停
    - 其余功能和常见的coding agent(linhai/claude code/ ...)相同
- [ ] 当前HostControl定义的process_create不支持wait_seconds为None，这不合理
  - 需要改为支持None以完成EtherGhost集成

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答
- 总是开启的插件默认在lifecycle.py中注册，视情况开启的插件在create.py中注册

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
