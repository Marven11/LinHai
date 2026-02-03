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
- [ ] 增强AgentMessage
  - 当前状态
    - AgentMessage由两部分组成：主messages列表和appending_messages
    - 在调用llm时将messages和（排序后）appending_messages拼接在一起
    - appending_messages用来放置一系列提示消息，如当前所在机器、token用量等
  - 问题
    - 在历史压缩时，messages中的一部分消息会被删除
    - 其中的.md prompt文件等会被直接删除，这会导致agent行为不一致，忘记用户/prompt要求等
    - 当前的init_messages将消息加入到messages列表中，同样会被删除
    - 当前的context_range_compress_*通过脆弱的index和消息类型判断start_id是否合适
  - 主要修复思路：在当前的messages前加上pinned_messages列表，固化一系列重要的消息
    - 包括：system prompt, 全局记忆, 用户-m指定的初始消息，用户-f指定的文件
  - 方案
    - 删除context_range_compress_*中验证start_id的逻辑，因为重要的消息全部都被移动到pinned_messages中
    - 删除init_messages的初始化逻辑，改为传入pinned_messages
      - 当前解析cli参数后会将init_messages分别传给agent和cli，需要改为传递pineed_messages
    - 重命名appending_messages为notification_messages，同时修改对应的函数名、参数和docstring等，以明确用途
    - 添加pinned_messages，总是排在messages前
      - 在生成消息列表准备调用llm时，按照顺序拼接pineed_messages, messages, notification_messages
    - 修改涉及到的所有unittest，修复所有pyright错误
  - 仔细规划，细化以上方案到DESIGN.md中
- [ ] 将PLANNING固化为内置功能，通过--plan参数开启
- [ ] 让INTRODUCTION_MACHINE_CONTROL仅在当前有超过1台机器时添加
- [ ] 重构ssh_host.py，抽离通过ssh创建trojan.py进程的功能和通过trojan.py操控目标机器的功能，以帮助未来添加docker容器控制等功能
- [ ] 重构ssh_host.py的_read_responses，在发现读取失败时立即退出并标记当前连接为失效，当前的以及之后调用这个对象都只返回连接失效
  - TODO 需要仔细规划
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
- [ ] 为load_image和ImageMessage加上指定图片质量的功能
  - 当前问题：
    - agent不支持预览图片，查看图片时只能完整加载图片
    - 这也导致每张图片都被标记为大消息
    - 这也导致如果加载了过大的图片
  - 需要添加
    - 为load_image添加一个必要参数quality
      - 可为compressed或者raw
      - 当为compressed的时候将图片等比例压缩到大约512x512的分辨率
        - 尝试使用公式(h * w / 512 / 512) ** 0.5估算放大倍率
    - 修改ImageMessage
      - 添加文字消息说明当前是被压缩的图像还是原始图像，图像分辨率又怎么了
      - 文字消息尽量简洁，例如“下方的图像以原始分辨率加载/被...，原始分辨率为xxx，....”
      - 提供一个估算Token用量的函数，根据当前的分辨率估算token用量
        - 我们知道kimi k2处理一张图片时会先经过2x2下采样然后14x14分块，所以对应原图应该是一块28x28的区域为一个token
        - 因此可以使用公式估算celi(h / 28) * celi(w / 28)
    - 修改当前处理大消息的逻辑
      - 对于ImageMessage，根据估算的token量是否大于800判断是否需要标记为大消息
  - 测试
    - load_image的quality参数
    - 压缩图像是否会正常等比例压缩
    - ImageMessage的估算token用量功能是否对于压缩图像和原始图像都工作正常
    - 大消息是否可以正确标记过大的ImageMessage为大消息

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
