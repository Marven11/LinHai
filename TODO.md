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
- [ ] 添加初始化配置的功能
- [ ] 当前展示缓存是否失效的功能有问题
  - 问题: 在历史压缩或者忘记大消息时会调用多次count_invalidate_cache，导致出现多条大消息
  - 问题：在系统消息被修改（如增减工具）等时候消息缓存实质上失效
  - 设计：添加一个动态的检查消息缓存是否失效的机制，在当前回答的缓存token数量少于所有输入token的五分之一时报告消息缓存失效
  - 解决
    - 完全删除count_invalidate_cache函数不再使用
    - 让update_cumulative_usage在接收到的AnswerTokenUsage中缓存token过少时发送Notice
- [ ] 让agent在被VolcanoDeepseekFixPlugin提醒时知道是哪个工具格式出问题
  - 方案：让VolcanoDeepseekFixPlugin不提示次数（因为没有用）而是提示标记附近的内容（100字符）
- [ ] 当前的process_stdio_write和process_stdio_read不返回json而是返回格式化后的字符串，这样无法完成下一个任务
  - 为每个HostControl添加process_stdio_write_structured和process_stdio_read_structured函数
  - 让process_stdio_write和process_stdio_read均使用process_stdio_write_structured和process_stdio_read_structured函数以遵守DRY
- [ ] 添加控制机器时的权限提升功能
  - 问题: agent在管理本地机器/ssh机器时，即使有sudo也无法修改root的文件 - machine_control提供的write_file等工具只能以当前用户的权限进行
  - 解决: 让agent可以连接sudo运行的trojan.py为一个新的机器
    - agent应该可以完成以下流程
      - 使用switch_machine切换到目标上并上传trojan.py到/tmp
      - 使用process_create运行`sudo xxx trojan.py`
      - 使用connect_privileged_trojanpy工具连接trojan.py，产生一个新的机器
  - 参考linhai/machine_control/ssh_host实现linhai/machine_control/privileged_trojanpy
    - 初始化时传入对应的HostControl以及pid
  - 实现connect_privileged_trojanpy
    - 需要支持自定义机器名字和机器描述
  - 全面编写对应unittest
- [ ] 当前on_tool_result的命名不合适，改为after_toolcall
  - 需要同时处理类型名、函数名、变量名等
  - 需要搜索on_tool和ontool不区分大小写以查看是否还有遗漏，完成任务前必须确认没有遗漏
  - 需要保证unittest不失败，pyright linhai/没有错误
- [ ] 改进linhai/cli/messages_list.py性能
  - 当前状态：自动滚动到底部的消息列表
  - 当前问题：在agent长时间运行后存在大量消息widget卡死界面
  - 主要改进：在没有向上滚动时隐藏上方看不见的消息，在有消息被隐藏时在消息列表最顶部显示一个“展示被隐藏的消息”按钮
  - 设计
    - 添加一个timer每0.05秒检查一次
    - 在自动滚动开启时：
      - 如果消息多于50条且消息列表widget高度高于“当前message list高度*10+200”则隐藏最上方的一个widget,按照原有顺序保存到列表中
    - 点击按钮后
      - 显示所有被隐藏的消息
    - 无论有没有隐藏/显示消息都sleep 0.05秒等待界面刷新
  - 以上设计难以验证，需要严格按照官网文档编写测试
    - 在有大量消息且开启自动滚动时上方有多条消息被隐藏
    - 滚动到上方时消息被逐个恢复且顺序和被隐藏前保持相同
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
- [ ] 我们需要用更加简洁的设计复刻openclaw的核心功能
  - openclaw的核心功能：
    - 从各个IM接收用户消息并转发给agent, agent可以通过id等回应用户
    - agent可以暂停等待输入，但是暂停后每隔一段时间就会收到一条心跳消息而被打断暂停
    - 其余功能和常见的coding agent(linhai/claude code/ ...)相同
- [ ] 当前HostControl定义的process_create不支持wait_seconds为None，这不合理
  - 需要改为支持None以完成EtherGhost集成
- [ ] 支持配置是使用本地EtherGhost还是EtherGhost API

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答
- 总是开启的插件默认在lifecycle.py中注册，视情况开启的插件在create.py中注册

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
