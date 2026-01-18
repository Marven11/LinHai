# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] 删除run_command工具，完全去除“运行命令”的概念并创建process管理工具替代run_command的功能
  - 问题：
    - 我们不知道启动的进程是否会等待读取stdin, agent总是分不清什么时候使用run_command什么时候使用终端
    - 根源在于agent根本不应该事先判断程序应该用什么工具
  - 查看prompt是否需要修改
  - 这是一个较大的重构，仔细规划
  - process_create工具
    - 使用传入的命令创建一个进程，等待几秒后检查。
      - 如果程序已经关闭则提供pid, 返回码，stdout和stderr
        - 如果返回码非0则视为工具执行失败
      - 如果程序仍然在运行则返回pid, stdout和stderr并给出message“程序仍然在运行”，将创建的进程对象放入字典中
    - 有以下参数
      - 命令：命令是一个list[str]，创建进程时设置shell=False
      - wait_second: 创建进程后等待几秒检查，默认1秒
        - 为了避免在程序退出后仍然等待，实际上每0.1秒就检查一次，直到达到wait_second限制或者发现程序退出
  - process_stdio_write工具
    - 向stdin写入
    - 参数pid
    - 参数content: 需要写入的字符串
  - process_stdio_read工具
    - 读取内容
    - 同时读取stdout和stderr并返回内容
    - 参数pid
    - 参数unescape_ansi: 是否反转义ansi序列，默认为true,用于避免在输出中包含大量ansi字符。
  - process_wait工具
    - 带超时的等待进程
    - 参数pid
    - 参数timeout: 等待几秒，如果传入大于3600的值则报错
  - process_kill工具
    - 参数pid
    - 参数graceful: 是否优雅杀死程序
    - 必须从字典中找到进程，如果找不到则报错“找不到进程，必须传入当前工具组创建的PID”
  - 记得使用目标系统的编码
  - 需要让master_host和ssh都支持新的process工具
- [ ] 给工具调用添加 on_machine 参数，强行指定工具在哪台机器上使用
  - 要求定义和with_secret一样定义在参数的外边
  - 考虑在连接机器后再添加 system prompt 介绍对应的属性，像secret system一样
  - 添加插件：如果连续 3 次使用同一个 on_machine，且 on_machine 和当前 machine 相同则开始警告
    - 如果有工具没有使用on_machine或者on_machine不同则清除计数器
- [ ] 为以上新功能添加unittest
- [ ] unittest警告大量测试没有被await，查一下怎么回事，让unittest正确运行而不产生警告
- [ ] 修复所有unittest的错误和警告

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

- [ ] 添加一个列出所有 terminal 的工具
- [ ] 重构工具调用结果的回调函数，仅提供一个工具调用结果的回调而不是分成多个
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
