# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [x] 当前SecretInterceptorPlugin有很大问题
  - 使用Test Driven Development，删除测试当前被重构逻辑的测试
    - 测试：如果没有指定with_secret，结果/错误信息中包含secret值，应该完全拦截
    - 测试：如果没有指定with_secret，结果/错误信息中不包含secret值，应该完全不拦截
    - 测试：如果指定with_secret，结果/错误信息中包含secret值，应该替换为`<$KEY$>`占位符
    - 测试：如果指定with_secret，结果/错误信息中不包含secret值，应该完全不拦截
    - 测试：如果指定的with_secret不完全，结果/错误信息中包含没有在with_secret中指定的secret值，应该完全拦截
    - 测试：如果指定的with_secret不完全，结果/错误信息中不包含没有在with_secret中指定的secret值，应该替换为`<$KEY$>`占位符
  - 重写
    - 当工具成功/失败时
      - 如果指定了with_secret: 替换其中的secret值为对应的`<$KEY$>`占位符并**跳出if让后面的逻辑检查替换后的结果**而不是直接退出
      - 如果（仍然）包含任何secret值：拦截
    - 当工具被跳过时：什么都不做
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
- [ ] 在配置中支持对机器设置命令白名单
  - 可能需要考虑如何实现检测通过终端执行的命令
- [ ] 查看tiktoken的文档，改进当前检查工具输出长度的逻辑和配置，使用tiktoken检查工具输出的token数量
- [ ] 让process_create在程序超时仍然运行的时候读取当前的stdout和stderr的已有内容并返回
  - 读取成功时在消息中添加“至今为止该进程已输出到stdout/stderr的内容”
  - 读取stdout/stderr超时则跳过并在message中添加读取stdout/stderr超时
  - 添加unittest检查读取stdout+stderr时，一个超时后另一个的内容是否会正常返回
- [ ] 让process_stdio_read顺便检查当前程序是否已经退出，如果退出则在消息中加上“注意：当前程序{pid}已经退出”
- [ ] 添加一个llm manager
  - 当前问题: 
    - 配置使用什么llm完全由agent控制，agent不应该关心llm api返回什么错误
    - 但是llm api有时会返回429或者报告文本长度过长，我们希望在这个时候临时轮换llm，但是agent不应该实现这个逻辑
    - 而且当前Agent类需要管理当前使用什么llm，这不太合理
    - 而且各个subagent或者未来的parallel agent可能需要同时使用当前配置的llm
  - 设计一个LlmManager管理所有llm，而不是让agent获得一个llms列表
- [ ] 添加初始化配置的功能

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
