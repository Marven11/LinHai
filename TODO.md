# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] linhai/machine_control/master_host/master_host.py等文件中的process_create等工具没有使用`<<>>`组织内容，而是使用了json
  - 检查所有构造ToolResultSuccess和ToolResultFailed的地方，保证传入的不是json而是使用`<<>>`组织的内容
- [ ] 添加一个列出所有 terminal 的工具
- [ ] 重构工具调用结果的回调函数，仅提供一个工具调用结果的回调而不是分成多个
  - 需要规划，统计当前插件等会如何使用这些回调，重构后应该将这个回调设计成什么样
  - 当前有多个关于工具调用的回调，这不合理
  - 需要重构，改为只提供一个回调on_tool_result，删除其他回调
  - 需要重构，让其他插件都只使用这一个回调
  - 直接在调用回调函数时提供工具调用的状态：成功、失败、被跳过
- [ ] 为上面的功能添加unittest
- [ ] 查看修复所有unittest的错误和警告

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
- [ ] 添加插件检查读写文件冲突：检查是否在读取一个文件后立即写入
- [ ] 在配置中支持对机器设置命令白名单
  - 可能需要考虑如何实现检测通过终端执行的命令
- [ ] 添加插件：在工具失败且参数中包含为list[str]的with_secret时，提醒agent with_secret应该在参数外
- [ ] 添加插件：在没有使用with_secret且参数中包含`<$KEY$>`wrapper时则警告
- [ ] 给run_command添加参数expect_statuscode: 要么为整数，要么为"nonzero"
  - 有时候agent要检查文件里没有什么，但是因为grep返回非0值而打断其他工具调用
- [ ] run_command应该默认使用/usr/bin/env sh, agent不知道如何处理非bash的转义
- [ ] 启动时塞一条runtime message，告知“当前时间为...初始pwd为...” 防止agent不知道当前时间，防止切换目录后忘记当前目录
- [ ] ToolCallResultMessage接受参数的repr不合理，应该接受参数本身（一个字典），然后在to_llm_message中再转换为repr
  - 这样我们可以
    1. 在一个地方管理如何转为repr
    2. 保存后可以在json中直接查看object形式的参数
  - 需要检查转为repr后是否设置了maxstring=100限制字符串长度
- [ ] asyncio.iscoroutinefunction 将在 python 3.16 中被移除，需要改成 inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
