# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 重构工具系统，添加MachineControl类和MasterHostControl类，用于管理所有和本机交互的工具
  - 现在的一系列工具本质上都是控制本地机器的工具：
     "http_request","run_command","change_directory","create_terminal","send_keys_to_terminal","send_string_to_terminal","read_terminal_screen","close_terminal","read_file","write_file","append_file","replace_file_content","list_files","get_absolute_path","run_sed_expression","modify_file_with_sed","insert_at_line",
  - 为了未来支持SSH远程控制其他机器，需要移动这些工具的定义
    - 先把linhai/tool/tools复制到/tmp/tools_backup备份，然后再慢慢cp后改
    - 你也许想要使用git diff在移动后查看，但是git diff会被subagent阻止，因为你原则上不应该使用git命令
  - 将这些工具移动到linhai/machine_control文件夹
    - 创建linhai/machine_control/master_host文件夹用来保存上方一系列工具的实现
  - linhai/machine_control/master_host.py: MasterHostControl类
    - 负责调用linhai/machine_control/master_host中保存的以上工具，工具实现需要和之前相同
    - 需要编写测试尝试通过其调用一些工具
  - linhai/machine_control/main.py: MachineControl类
    - 负责注册工具，在拿到工具的参数后，根据target_machine找到对应的HostControl类，并根据工具名称调用对应的HostControl的对应函数
      - target_machine是MachineControl的属性master_host
    - 负责注册一个特殊工具switch_machine用于切换机器，list_machines用于列出机器
      - list_machines包括机器的ID("master_host"等)和机器的描述
      - switch_machine调用后发送CliRuntimeNotice提醒用户
    - 负责添加appending_message, 在其中提示当前在什么机器上
      - 只需要添加短短一句RuntimeMessage: `当前在{machine_id}上`
      - 参考: linhai/agent/plugin.py
    - 注意MachineControl在create_agent流程中的正常时机
      - 因为其需要通过group_chat实现: 调用tool_manager注册工具, 调用lifecycle注册插件，所以需要在这两个
      - 不要try catch group_chat抛出来的RuntimeError: 如果group_chat抛出了RuntimeError就说明你的注册时机有问题，修复你的代码
    - 需要编写测试
      - 尝试通过其调用一些工具
      - 确认在正常的create_agent流程中可以正常注册工具
      - 确认appending_message被正常添加
  - linhai/tool/tools中没有列出在上方的工具是和控制本地机器无关的工具，如fetch_article, search_web, sleep等:
    - 不要移出linhai/tool文件夹
    - 创建一个linhai/tool/general.py文件用来保存这些工具的定义
    - 因此，linhai/tool/tools中的代码要么移动到linhai/tool/general.py要么移动到linhai/machine_control/master_host
- [ ] 添加SshMachineControl类
  - 目前不需要实现所有MasterHostControl类支持的工具
  - 你需要实现一个trojan.py来在远程服务器上实现这个功能，为了不和agent重名我们将远程控制进程称为trojan
  - 连接控制流程
    - 连接ssh，在目标上的/tmp文件写入trojan.py
    - 检查`/usr/bin/env python3 -V`是否是python3.6以上
    - 启动`/usr/bin/env python3 <trojan.py的临时地址>`并通过stdio通信
  - trojan.py
    - 和trojan.py的连接协议使用json rpc
    - trojan.py应该不需要使用python标准库之外的库
  - 只需要实现这些工具
     "run_command","change_directory","read_file","write_file","append_file","replace_file_content","list_files","get_absolute_path","run_sed_expression","modify_file_with_sed","insert_at_line",
  - 不需要这些
     "http_request","create_terminal","send_keys_to_terminal","send_string_to_terminal","read_terminal_screen","close_terminal",
  - 连接./.secret.todo.md中提到的机器测试，因为本文件会被添加到git仓库所以不能在这里提到

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] 禁止无用的run_command
  - 完全禁止直接使用sed命令，提示：“禁止直接使用sed命令查看或修改文件！”
    - 例外：使用`|`或者`>`重定向，可以简单地通过检查相关字符实现
  - 禁止使用grep搜索已经读取了的文件
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
