# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [ ] 我们需要做出充足准备测试以下功能
  - 在./tmp写一个脚本，手动构造SshMachineControl并用其在dell nixos的/tmp中写入一个测试文件并读取，打印结果
    - 脚本要求
      - 少于200行
      - 不使用多余的print和注释
      - 缩进不多于4层
- [ ] 当前trojan.py仍然不支持并发处理请求
  - 当前：为每个请求创建queue并处理，处理请求时使用非并发的循环+await
  - 目标设计：
    - 接收到请求后立即创建task处理对应功能
    - task异步运行
    - task完成后将响应写入queue
    - 定时从响应queue中取出响应并写进stdout
    - 去除无用的请求queue
- [ ] 重新测试第一个任务中的脚本是否可以使用
- [ ] 为SshMachineControl添加两个方法用于支持transfer_file功能的实现
  - upload_file_concurrent: 接收一个bytes，分块并发上传到目标，写入到指定文件路径
    - 检查文件路径是否已经存在，如果存在则报错
    - 在/tmp新建临时文件夹，名字随机
    - 将文件内容每32k分块，对于每块分别调用trojan.py上传到临时文件夹中，文件名以对应的offset命名
      - 注意文件名，需要计算需要的0的数量并补足足够的0
    - 按照offset拼接所有文件为一个文件，然后移动到指定文件路径
  - download_file_concurrent: 并发下载目标上的一个文件，保存到master_host上的指定路径
    - 获取目标文件的大小，每32k分块，对于每块分别调用trojan.py并发下载每一块文件，然后拼接回来，写入master_host
  - 注意最大并发数量为8，且最多重试3次
  - 需要对应修改trojan.py
  - 为这两个方法添加unittest
  - 为了接口干净，也可以为master host实现这些方法，但是完全不需要并发（因为没有网络请求），只需要简单地复制文件即可
- [ ] 基于第一个任务中的脚本在./tmp编写第二个脚本测试upload_file_concurrent和download_file_concurrent的功能
- [ ] 运行unittest确保在实现transfer_file之前基本正常
- [ ] transfer_file功能: 将文件从一台机器传送到另一台机器上
  - 参数：from_filepath, from_machine, to_filepath, to_machine
  - 逻辑
    - 检查from_machine和to_machine是否不同
    - 将文件从from_machine上下载到master_host的临时路径
    - 将文件从master_host上传到to_machine
- [ ] 基于第一个任务中的脚本在./tmp编写第三个脚本测试transfer_file的功能
- [ ] 在终端中启动linhai并测试
  - 打包当前目录为/tmp/linhai.tar.gz
  - 确认当前时间，然后在终端中启动`uv run python -m linhai -m '@nothink 将/tmp/linhai.tar.gz上传到dell nixos的/home/cube文件夹然后退出'`
  - 使用tab选择对话框然后使用pagedown向下滚动查看linhai的最新输出
  - 自己登陆dell nixos然后查看/home/cube是否有对应文件，时间戳是否和linhai的启动时间一致

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
- [ ] 添加插件检查读写文件冲突：检查是否在读取一个文件后立即写入
  - 问题：agent有时会在一个回答中调用多个工具，在调用读取文件之后立即尝试修改，即使此时根本没有看到文件内容。这是模型幻觉
  - 设计: 插件维护一个已经读取文件的列表，在回答生成之前清空列表，调用读取文件工具时将文件路径添加到列表，调用写入文件工具时检查路径是否在列表中
  - 设计：仅在当前机器为master_host时检查
- [ ] 在配置中支持对机器设置命令白名单
  - 可能需要考虑如何实现检测通过终端执行的命令
- [ ] 启动时塞一条runtime message，告知“当前时间为...初始pwd为...” 防止agent不知道当前时间，防止切换目录后忘记当前目录
- [ ] ToolCallResultMessage接受参数的repr不合理，应该接受参数本身（一个字典），然后在to_llm_message中再转换为repr
  - 这样我们可以
    1. 在一个地方管理如何转为repr
    2. 保存后可以在json中直接查看object形式的参数
  - 需要检查转为repr后是否设置了maxstring=100限制字符串长度
- [ ] 让find_most_similar_in_files使用`<<>>`组织内容
  - 问题：当前格式使用repr，导致文件内容字符串被转义
  - 解决方案：仿照其他使用`<<>>`组织内容的地方，用`<<alternative>>`包裹每个可能的匹配
- [ ] 改进OnlyReasoningPlugin的RuntimeMessage
  - 当前的消息内容太吓人了
  - 改进：`检测到在思考后没有输出任何内容而是在</think>标签前就输出了工具调用等，应该在</think>标签后输出实际内容`
- [ ] asyncio.iscoroutinefunction 将在 python 3.16 中被移除，需要改成 inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
