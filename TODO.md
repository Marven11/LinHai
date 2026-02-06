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
- [ ] 为planning添加插件，提醒修改STATUS.md和TODOLIST.md
  - 在不开启planning时不注册插件
  - 插件检查after_message_generation
  - 如果修改了则清空counter和notification_message
  - 如果至少连续3次没有修改STATUS.md则使用update_notification_message警告agent
    - 你已经连续x次没有修改STATUS.md，你偏离计划了吗？
  - 如果至少连续8次没有修改TODOLIST.md则使用update_notification_message警告agent
    - 你已经连续x次没有修改TODOLIST.md，你偏离任务了吗？你应该如何修改TODOLIST.md?当前任务是否需要分解？当前任务是否需要被推迟？
- [ ] 为planning添加插件，在用户输入消息后添加RuntimeMessage
  - 在不开启planning时不注册插件
  - 不使用update_notification_message而是add_new_message
  - 内容：“用户提出的问题？指示？重新规划？重新设计？规划检查？优先规划？记录用户原文？”
- [ ] 让INTRODUCTION_MACHINE_CONTROL仅在当前有超过1台机器时添加
- [ ] 重构ssh_host.py，抽离通过ssh创建trojan.py进程的功能和通过trojan.py操控目标机器的功能，以帮助未来添加docker容器控制等功能
- [ ] 重构ssh_host.py的_read_responses，在发现读取失败时立即退出并标记当前连接为失效，当前的以及之后调用这个对象都只返回连接失效
  - TODO 需要仔细规划
- [ ] 拆分app.py的实现
  - 问题：当前app.py同时处理消息列表和低栏、顶栏等内容，不利于重构
  - 重构：我们实现一个linhai/cli/messages_list.py拆分app.py中的**所有**处理新消息的逻辑，至少完成以下几点
    - 所有需要移动的逻辑
      - 监听处理"parsed_agent_answer", "ui_log"
      - 新消息生成和管理
        - 创建并管理VerticalScroll(id="chat-container")
        - 显示self.init_messages
        - mount新的消息
      - 管理自动滚动
    - 所有不需要移动的逻辑
      - 欢迎界面和ASCIIART
      - 管理self.agent_task
      - 管理底栏和用户文本输入框
    - 考虑移除
      - self.messages: 只在compose中才被使用，compose仅在初始化时调用，此时self.messages仅含有初始消息。此时直接使用self.init_messages即可
    - 目标
      - 移动监听agent新消息的逻辑
      - 移动创建和管理新消息widget的逻辑
      - app.py不再直接管理任何消息
      - 不要在app.py中处理自动滚动
    - 修改对应的unittest以适应新的重构，保证行为完全一致
- [ ] 重构cli提升速度
  - 当前问题: 长期运行之后界面上有大量的message和CliRuntimeNotice消息没有被折叠
  - 当前问题：没有一个良好的机制遍历MessageWidget中的ToolCallWidget中的工具调用是否正确，以及获取工具名
  - 当前问题：没有一个良好的机制同时将MessageWidget和其对应的RuntimeMessageWidget移动到历史消息中
    - 可能需要加上一个widget将二者包裹起来，或者直接将RuntimeMessageWidget塞进MessageWidget
  - 规划
    - 重构设计界面，不再直接将所有消息都堆在页面中
    - 消息列表瀑布流界面
      - 最上面是“展开历史消息”方框按钮
      - 然后是一系列只占一行的“被折叠的消息”和runtime message交替出现
        - 每个被折叠的消息只占一行，其中显示[-]表示可以点击展开，然后跟着一系列工具名，如`[-] read_file, read_file`
        - 如果工具调用有错则不展示工具名而是`<bad toolcall>`
        - 可以点击展开，点击展示原有的消息
      - 然后是最新的消息和最新的runtime message
- [ ] 为secret添加一个disabled_in_toolcall_argument选项
  - 问题：有时候我们需要阻止secret泄漏,但是不希望agent在工具调用中使用secret以防止secret泄漏到其他地方
  - 设计: 
    - 部分secret可以被设置为disabled_in_toolcall_argument，被设置为disabled_in_toolcall_argument的secret不会在函数参数中被替换，仅可以在结果中被替换
    - disabled_in_toolcall_argument默认为False
  - 添加测试
    - 在prompt中有相关说明，说明disabled_in_toolcall_argument的作用：
      - “disabled_in_toolcall_argument用于非常机密的secret，disabled_in_toolcall_argument=True的secret禁止在函数参数中使用以完全避免泄漏”
      - “这意味着你不能查看也不能使用这些secret，只能用with_secret将这些secret遮住”
    - 在secret被列出时同时提供disabled_in_toolcall_argument的值
    - 同时使用with_secret指定一个disabled_in_toolcall_argument=True的secret1和一个disabled_in_toolcall_argument=False的secret2
      - 如果函数参数中有secret2则报错“secret被禁止在函数参数中使用”
- [ ] 参考openclaw的设计添加类似openclaw的全局记忆功能
  - 添加一个--claw参数，帮助为“打开Continuous Living Autonomous Worker模式”
  - 当前这个参数仅检查~/.local/share/linhai/claw/有没有创建，如果有则创建
  - 编写相关unittest
  - 推迟：编写相关prompt
- [ ] 将LINHAI.md迁移为AGENTS.md
  - 问题: 当前LINHAI.md包含的实际是对agent的要求prompt，不希望模型修改
  - 问题：我们在将linhai用作coding agent时不希望linhai修改全局记忆
  - 重新设计
    - 读取 https://agents.md/ 网页并下载到./docs/AGENTSMD_WEBSITE.md中
    - 【注意】不要向后兼容，也不要修改当前的全局记忆文件，这个我之后自己去改
    - 流程
      - 搜索“全局记忆”术语改为“全局指导”
      - 搜索GlobalMemory改成GlobalPrompt
      - 搜索“路径记忆”术语改为“路径指导”
      - 搜索PathMemory改成PathPrompt
      - 修改所有有关的prompt、类名和文件名等
      - 重新搜索以上关键词，如果仍有则将任务标记为未完成，继续修改

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
