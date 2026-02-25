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
- [ ] 添加初始化配置的功能
- [ ] 让http_request在master_host上的实现也返回header和status code,同时如果body大于5000个字符则将body转储到conversation文件夹并返回路径而不是直接返回
  - 问题：如果响应是长json则模型无法直接读取，也无法直接用jq处理（因为长消息会被分割到多个文件）
- [ ] 当前on_tool_result的命名不合适，改为after_toolcall
  - 需要同时处理类型名、函数名、变量名等
  - 需要搜索on_tool和ontool不区分大小写以查看是否还有遗漏，完成任务前必须确认没有遗漏
  - 需要保证unittest不失败，pyright linhai/没有错误
- [ ] 为lifecycle添加before_add_new_message回调
  - 问题：当前大消息标记hook了工具调用结果，但是实际上需要hook添加新消息
  - 需要编写对应的测试确保回调可以正常拿到消息的引用
- [ ] 当前大消息标记和secret系统不太兼容
  - 问题：大消息标记和secret系统都hook了工具调用结果，但是一个保存了工具调用结果的引用，一个替换了工具的结果，导致大消息标记找不到原有结果
  - 解决：让大消息标记使用before_add_new_message回调拿到消息而不是使用工具调用结果的hook
- [ ] 改进linhai/cli/messages_list.py性能
  - 当前状态：自动滚动到底部的消息列表
  - 当前问题：在agent长时间运行后存在大量消息widget卡死界面
  - 主要改进：在没有向上滚动时隐藏上方看不见的消息，在用户向上滚动时重新显示回来
  - 设计
    - 添加一个timer每0.05秒检查一次
    - 在自动滚动开启时：
      - 如果消息多于20条且消息列表widget高度高于“当前message list高度*2+200”则隐藏最上方的一个widget,按照原有顺序保存到列表中
    - 在自动滚动关闭时：
      - 自动滚动关闭说明用户有可能向上滚动
      - 如果当前滚动位置距离顶部少于“当前message list高度*2”则按照顺序恢复最靠近的消息（也就是所有被隐藏的消息中最底部的消息），显示
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
- [ ] EtherGhost集成
  - 这是一个非常复杂的集成，需要仔细规划，**完全测试**
  - 参考当前的SSH机器控制，实现通过EtherGhost控制远程机器的功能
  - EtherGhost是一个python库，源码在../EtherGhost，需要先通过uv add添加依赖，为了使用新的send_http_request函数需要从dev branch而非pypi安装
  - 实现EtherGhostMachineControl
    - http_request: 在传入send_http_request不支持的参数时报错：“EtherGhost不支持xxx”
    - change_directory: 获取当前pwd直接返回错误
      - 使用get_pwd获得当前路径
      - 错误内容：“因webshell限制，EtherGhost不支持change_directory，当前路径固定为xxx”
    - process_create
      - EtherGhost对进程管理的支持不好，管理一个进程需要启动一个僵尸马
      - 向agent解释：当前通过EtherGhost控制机器。EtherGhost使用php shell_exec等函数运行命令，任何长时间运行的命令都会导致超时
      - 我们修改process_create的实现
        - agent有时会传入wait_seconds<10
          - 此时为了方便agent我们忽略这个较小的wait_second
          - 直接用execute_cmd运行命令并警告agent“EtherGhost不支持指定wait_seconds”
        - 在wait_seconds为None或者小于10时使用execute_cmd运行命令，并在超时时不返回pid而逝
        - 在wait_seconds超过10时返回错误报告“EtherGhost不支持长时间运行命令，因此在控制EtherGhost机器时不能传入wait_seconds”
    - process_*
      - 因上述原因，除了process_create之外的process_*函数均只能返回错误：“EtherGhost不支持xxx，仅支持...”
    - terminal_*和get_terminals
      - 同样的，webshell很难支持终端，返回错误: “EtherGhost不支持terminal_*，请使用...”
    - 读写文件
      - 模型修改文件时首先用get_file_contents获取文件内容，然后put_file_contents
      - 逻辑参考MasterHostControl的实现
    - get_absolute_path: 执行命令realpath xxx并返回结果
    - read_file_with_sed和modify_file_with_sed
      - 检查目标上有没有sed然后执行sed
      - 如果没有sed应该返回一个魔数uuid（启动时随机生成）以和正常的结果区分
      - if (sed do not exists); then echo {uuid}; else sed xxx; fi
    - download_file_concurrent和upload_file_concurrent: 对接download_file和upload_file
  - 实现ether_ghost_connect_webshell和ether_ghost_get_connection_args_definition
    - 支持PHP一句话、两个PHP冰蝎(behinder)、Linux Shell一句话
    - ether_ghost_connect_webshell至少需要传入传入type和connection_args
    - ether_ghost_get_connection_args_definition返回json schema结构化的定义，包含每个webshell类型的连接配置定义
      - 使用json: `{"type": "xxx", "connection_args_definition": {xxx}}`
  - 测试
    - 编写unittest
      - 测试EtherGhostMachineControl的所有功能
    - 在/tmp编写脚本
      - 使用EtherGhostMachineControl连接.secret-webshell中的测试webshell
      - 完成测试所有EtherGhostMachineControl的功能
  - 必须完成：包括新增unittest在内的所有unittest通过，/tmp的那个脚本成功连接并测试所有功能
- [ ] change_directory在当前目录不存在时会失败
  - 如果当前目录不存在则提示“原目录不存在，切换到了...”
- [ ] master_host的http_request硬编码了conversation路径
  - 原因：http_request无法获取conversation路径但在先前commit中仍然强行设计为保存到conversation目录，且没有注意到http响应不需要保存到conversation目录
  - 修复：改回保存到临时文件，和那个commit修改前一致
- [ ] 支持配置是使用本地EtherGhost还是EtherGhost API

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答
- 总是开启的插件默认在lifecycle.py中注册，视情况开启的插件在create.py中注册

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
