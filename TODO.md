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
- [ ] 重构ssh_host.py，抽离通过ssh创建trojan.py进程的功能和通过trojan.py操控目标机器的功能，以帮助未来添加docker容器控制等功能
- [ ] 重构ssh_host.py的_read_responses，在发现读取失败时立即退出并标记当前连接为失效，当前的以及之后调用这个对象都只返回连接失效
  - TODO 需要仔细规划
- [ ] 让ToolCallWidget在看到segment结束时在五秒后折叠自己
  - 设计
    - 在if self._segment["is_finished"] and self.timer:设置一个timer更新自己
    - 如果当前为语法错误的工具调用，折叠为`<error toolcall>`
    - 可以点击展开，这意味着你需要抽象出当前渲染完整内容的代码为一个独立的方法
    - 折叠后的形式类似python，但是简化显示传入参数以缩短长度
      - 如果参数是dict/list,递归处理=
        - 如果结果过长（长于80字符）则只展示第一个item
          - 如`{"...": "...", ...}`或者`["...", ...]`
      - 如果参数是atom且不是字符串，原样显示。因为True等足够短
      - 如果参数疑似路径(绝对路径/相对路径)，则仅展示文件名，其他地方用省略号省略
        - 如`filepath=..."example.py"`，注意省略号在外面
      - 如果参数是字符串，用带双引号的省略号表示其是被省略的字符串，`"..."`
    - 你需要抽象将工具调用JSON转成折叠形式的实现为一个辅助函数，并单独编写测试
  - 测试
    - 完整测试生成折叠形式的函数
    - 完整按照textual的官方文档编写CLI测试，用于测试展开折叠工具调用的功能
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
- [ ] 我们需要用更加简洁的设计复刻openclaw的核心功能
  - openclaw的核心功能：
    - 从各个IM接收用户消息并转发给agent, agent可以通过id等回应用户
    - agent可以暂停等待输入，但是暂停后每隔一段时间就会收到一条心跳消息而被打断暂停
    - 其余功能和常见的coding agent(linhai/claude code/ ...)相同
- [ ] 完善claw功能
  - 当前: 在--claw参数被指定时，我们只新建了对应文件夹
  - 当前: claw定义了这五个核心的markdown文档: AGENTS.md  BOOTSTRAP.md  IDENTITY.md  SOUL.md  USER.md
    - 参考https://liruifengv.com/posts/openclaw-prompts/和./docs/openclaw-core-markdown
    - 但是和参考不同的是，我们将CLAW定义为Continuous Living Autonomous Worker
  - 在看到文件夹不存在时不仅新建文件夹，还初始化对应的文件
    - 需要初始化参考中提到的每一个markdown
    - markdown初始内容放在prompt.py中，每个为一个常量，内容和docs/openclaw-core-markdown完全相同
  - 添加一个claw的插件
    - 放在linhai/plugin/claw.py中
    - 插件在agent启动时将claw模式的介绍放进system prompt中
      - prompt模板放在prompt.py中
      - 用一段话介绍“用户用--claw模式启动你，你已经进入...模式，你不再是...而是...，你需要...”
      - 介绍每个claw核心文档
        - 并给出claw中的绝对路径，如果文件不存在则提示“文件不存在，无需在意”
        - 每个markdown仅用一段话介绍
    - 插件将claw文件夹文件内容加入到pinned message中
      - 检查每个文件是否都在claw中，如果有则添加
      - 你需要为AgentMessage添加一个方法add_pinned_message以符合极简的原则
  - 编写测试
    - 在文件夹不存在时正确新建文件夹并初始化每个markdown
    - 在文件夹存在且为空时不初始化每个markdown
    - 在指定--claw时system prompt添加对应章节
    - 在指定--claw时每个仍然存在于claw文件夹的markdown文件都被添加，额外的文件不被添加，被删除的文件不被添加

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
