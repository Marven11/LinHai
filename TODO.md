# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] 创建agent的逻辑linhai/agent/create.py过于复杂，需要改进
  - 现状
    - create_agent_from_config等初始化函数过于复杂，且包含大量默认参数，传参方式也不统一
    - _create_agent_from_config这个wrapper完全不需要存在
  - 期望设计
    - 设计一个AgentBuildContext类包含这些数据
      - group_chat, config, config_basedir, llm_name, checklist_path, git_diff_reviewer, violation_checker
      - 需要设计构造函数
        - 如果llm_name不存在则直接报错配置不正确，后续不再重新检查
        - 如果传入的llm_name为None则说明配置要求选择第一个llm，将llm_name设置为第一个llm的名字
        - 这意味着AgentBuildContext保存的llm_name不应该是None，只能是配置中存在的name
    - create_agent_from_config
      - 仅接收AgentBuildContext
    - _create_llm_instances
      - 仅接收AgentBuildContext
      - 保持返回`list[LanguageModel]`
      - 在创建OpenAi实例时传入name
    - OpenAi和LanguageModel
      - 添加get_name接口，返回当前llm的name
    - llm_names
      - 完全删除，因为每个llm的name都保存在对应的类中
    - `llm_name not in llm_names` - 之前已经检查llm_name的正确性，去除再次检查
    - _create_tool_manager
      - 仅接收AgentBuildContext
    - memory_file_path
      - 计算逻辑移动到_create_init_messages中
      - 不检查config_basedir的有效性
      - 处理相对路径、绝对路径和expanduser
    - _create_init_messages
      - 仅接收AgentBuildContext
    - 创建Agent类
      - llms_with_names - 改为llm列表，一个list[LanguageModel]
    - `machine_control.register_plugin(agent.lifecycle)`
      - 编写MachineControl.postinit并移动到其中，通过group chat调用postinit
    - `初始化Secret系统`
      - 移动到_create_tool_manager中
    - `git_diff_reviewer`, `violation_checker`, `if subagent_config and subagent_config.enable`, `IssueManager`
      - 新建_create_subagent并移动到其中
      - 也就是说如果没有开启subagent系统就不要初始化并注册IssueManager
  - 这是一个很大的重构，仔细思考，输出markdown规划然后仔细重构所有需要的地方

# 暂时搁置

- [ ] terminal tab
- [ ] 添加假设颠覆法
- [ ] minimax api不支持user消息的name=xxx不同，应该直接删除to_llm_message中生成的所有"name": xxx
- [ ] asyncio.iscoroutinefunction将在python 3.16中被移除，需要改成inspect.iscoroutinefunction

# 注意

- 在终端刚刚启动linhai时TUI焦点锁定在tab区域，需要按下tab键选择对话区域才能使用pageup/pagedown翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 
