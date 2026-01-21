# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] 重构linhai/agent/orchestration.py
  - 当前问题：嵌套函数太多，逻辑分散导致难以阅读和测试
  - 期望行为：绿灯、黄灯：不拦截，一分钟内清理过：仅拦截上下文清理工具（因为最近已经清理过），红灯且一分钟内没有清理过：拦截，仅放行上下文清理工具
    - 注意：llm返回的上下文信息有延迟，导致刚刚清理过仍然计算得到红灯
    - 注意：持续绿灯时可以重复提示
      - 旧有逻辑检测上一个状态是否是绿灯，据此判断是否需要重新提示
      - 在新实现中我们使用update_appending_message直接防止重复提示的出现，因此不需要避免“重复提示”
  - 删除last_threshold_state状态
  - 计算编排上下文函数
    - 根据当前状态和当前工具计算
    - 计算并返回以下信息：threshold_info, 红绿灯，一分钟前是否清理过，提示消息，ToolBlockDetailsDict
    - 合并这些函数的功能: _recently_called_cleanup_tool, get_tool_block_details, _determine_threshold_state, _build_threshold_message
      - 这意味着要删除这些函数
  - 插件仅通过“计算编排上下文函数”获得的信息判断是否拦截，仅从其中取出消息并发送
    - 这意味着插件完全不计算消息，不拼接字符串
  - 获得toolset的函数
    - 合并get_message_management_toolset和get_workflow_toolset
  - get_large_message_reprs
    - 完全删除，相关逻辑移动到token_manager.py中，让token_manager.py直接获取large_messages
  - 检查linhai/agent/orchestration.py是否在500行以内，如果没有则按照深层价值观继续重构
  - 重新读取文件逐个检查以上逻辑是否完成
  - 重写对应unittest重点检查“计算编排上下文函数”，要求逻辑和“期望行为”相同。如果有疑问参考原有unittest判断期望行为
- [ ] 运行并修复所有unittest


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
- [ ] 用户用-f指定的文件没有使用FileContentMessage，应该改正
  - 每当用户用-f指定一个文件时仅仅放入FileContentMessage即可，不需要添加“用户用-f指定...”和“文件内容如下”这些提示
- [ ] 查看tiktoken的文档，改进当前检查工具输出长度的逻辑和配置，使用tiktoken检查工具输出的token数量
- [ ] 修改change_directory提示的消息，使其包含原目录，如“从目录xx切换到了xx”
- [ ] 添加初始化配置的功能

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
