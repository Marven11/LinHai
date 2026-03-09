# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] 改进PromptFastAgentPlugin
  - 当前问题: PromptFastAgentPlugin仅被用于特定类型的llm，且不能在配置中自定义每个回答可以有多少个工具调用
  - 设计：让PromptFastAgentPlugin变成一个根据配置项开启的插件
  - 解决
    - 修改配置项支持配置每个llm的最大工具调用数量
      - 在agent.max_toolcall_for_llm中设置，键为llm的名字，值为数量
    - 不再默认注册PromptFastAgentPlugin，在配置了max_toolcall_for_llm时才注册
    - 修改PromptFastAgentPlugin使其接收max_toolcall_for_llm并在max_toolcall_for_llm中有当前llm时才据此打断llm
  - 添加配置
    - 在添加了对应配置项后agent会被打断
    - 在切换llm前会被打断，切换到没有工具限制的llm后不会被打断
    - 在切换llm前不会被打断，切换到有工具限制的llm后会被打断
    - 在切换llm前会被打断，切换到最大工具调用数量更多的llm后不会被打断
- [ ] linhai/plugin/security_config.py没有检查argv是否都是字符串，也没有检查argv是不是列表
  - 添加相关测试并修复，测试如果argv中包含数字会发生什么
- [ ] trigger_after_segment和trigger_after_segment_finished没有被良好测试
  - 每一个trigger调用都需要有对应的测试

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
  - 用户运行python -m linhai init可以打开初始化TUI页面，可以设置第一个llm的openai的base_url, api_key等
  - 参考https://github.com/Textualize/textual/blob/main/examples/calculator.py
- [ ] 我们需要用更加简洁的设计复刻openclaw的核心功能
  - openclaw的核心功能：
    - 从各个IM接收用户消息并转发给agent, agent可以通过id等回应用户
    - agent可以暂停等待输入，但是暂停后每隔一段时间就会收到一条心跳消息而被打断暂停
    - 其余功能和常见的coding agent(linhai/claude code/ ...)相同

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答
- 总是开启的插件默认在lifecycle.py中注册，视情况开启的插件在create.py中注册

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
