# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] 修改run_sed_expression的逻辑，完全禁止读取少量内容
  - 标准：少于100行且内容少于30000个字符
- [x] 重构clarification -> issue
  - 深层需求：
    - 将clarification重命名，并结构化创建的过程，统一“最低回复间隔”的逻辑
    - 根据issue的发送限额自动关闭subagent，不生成更多回答
    - 重写prompt使其没有逻辑冲突
  - issue包含
    - 请求者
    - 内容
    - ID
    - 最低回复间隔（新加的）
      - 当前固定“新的clarification在两分钟内禁止回答”
  - 每个subagent在创建issue时
    - 可以指定内容
    - 根据subagent的类型自动确定最低回复间隔
      - git diff reviewer提出的issue - 两分钟内禁止回答
      - 其他：可以立即回答
    - subagent的类型决定每个subagent最多可以提出多少issue
      - issue限额用尽后被关闭，不会生成新的回答
      - git diff reviewer只能生成一个issue
  - agent
    - 在收到issue时不会被提示“需要立即回答”
    - 可以在list_issue中查看每个issue可以在多久后回答
    - 提早回答issue时不会被提示“可以sleep”，只会被提示“先去做其他事情再回答！”

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] 重构compress_threshold_soft等
  - 0% - 50% 绿灯 - 标记消息
  - 50% - 70% 绿闪 - 标记消息
  - 70% - 90% 黄灯 - 清理垃圾消息
  - 90% - 100% 红灯 - 历史压缩
  - 如果在一分钟内调用过历史压缩或者清理垃圾消息则禁止调用历史压缩
  - 注意主要实现和重要的状态管理需要放在linhai/agent/orchestration.py中
- [ ] 改名--code-style选项为--checklist，同时修改代码内的表述
- [ ] 修改工具调用冲突的检测逻辑
  - 确认conflict_with是有向的: A标记自身和B冲突代表在一个消息内A不能在调用B之后调用，不代表B不能在A之后调用
  - 修改文件修改工具和文件读取工具的conflict逻辑：一个消息内修改工具不能在读取工具之后调用，读取工具可以在修改工具后调用
- [ ] 将git diff reviewer改为使用命令行选项打开而不是通过配置打开
- [ ] 添加一个`/subagent_start`命令手动启动subagent
  - 当前只需要手动启动git diff reviewer
  - 当前插件和手动启动两种方式都可以启动git diff reviewer，可能需要提取启动git diff reviewer的逻辑
- [ ] 重构prompt.py和SystemMessage，使system prompt的构造结构化
  - 当前主要包含四个部分：总览、各个部分的介绍、注意事项、示例
- [ ] secret系统
  - 当前问题: agent必须通过参数调用工具，但是其有时需要输入密码, token等敏感信息
    - 例如agent必须发送这样的工具调用`{"name": "xxx", "arguments": {"content": "password=123456"}}`，其中需要输入敏感密码123456
  - 设计secret系统
    - 配置
      - 用户可以使用在配置的`[tools.secret]`选项中配置secret配置文件路径的位置
      - secret配置文件的格式为toml格式，保存各个secret
      - 在配置中的secret键不用`<$$>`包裹，在agent使用时需要用`<$$>`包裹
    - secret设计
      - 一个secret包含键，值和描述
      - 键包含`[A-Za-z0-9-_]`字符，不以0-9开头且一般使用大写字母
      - 值是任意字符串，可为空
      - 描述是一小段话，字符串
      - secret键的`<$$>`格式
        - 在agent的上下文中，secret的键需要用`<$$>`包裹，如`<$OPENAI_API_TOKEN$>`
    - 工具调用
      - agent可以在调用工具时使用`with_secret`选项，选项的位置和`assert_success`同级 
      - `with_secret`是一个字符串的列表，包含当前工具调用使用的`<$$>`格式secret键
        - 如`["<$OPENAI_API_TOKEN$>", "<$SSH_PASSWORD$>"]`
      - agent如何通过`with_secret`在工具调用中包含secret值
        - `with_secret`被指定时, toolcall manager会:
          - 递归检查工具调用arguments中的每个值，将其中的`<$$>`格式secret键替换secret值
      - agent如何通过`with_secret`查看包含secret值的工具结果
        - 当secret配置文件被指定时，toolcall manager会注册一个插件拦截所有工具调用结果
        - 目前不能拦截所有传给agent的消息，例如subagent的issue不会被拦截，加上一条TODO注释说明
        - 在工具调用本身没有指定`with_secret`时
          - 如果工具调用的内容包含了任何secret值则拦截
          - 拦截返回一个新的RuntimeMessage，其中提示
            - `工具调用的结果包含<<$$>格式secret键>的内容，已拦截`
            - `如果需要查看内容则需要使用with_secret指定对应的键，其中的secret值会被secret键拦截`
        - 在工具调用本身指定了`with_secret`时
          - 返回一个MaskedToolCallResult，包含原有的工具调用message
          - 在其的to_llm_message中
            - 将工具调用结果中将所有的secret值改成对应的secret键
            - 提示结果中包含什么secret键
            - 返回`<<masked>><<messaage>>工具内容包含<<$$>格式secret键>, <<$$>格式secret键>secret的内容，已替换<<message>><<content>>（被替换后的工具结果）<<content>><<masked>>`
    - appending message
      - 如果没有配置secret则不添加对应message
      - 添加appending message告知当前可用的<$$>格式secret键和描述
      - 例如`当前可用secret键: <$OPENAI_API_TOKEN$> - 调用OpenAI的API token; <$SSH_PASSWORD$> - SSH私钥的解锁密码`
    - 示例: 编写包含api token的python脚本
      - 用户配置secret配置文件，在其中包含`OPENAI_API_TOKEN=sk-xxx`
      - agent调用write_file工具:
        - `{"name": "write_file", "with_secret": ["<$OPENAI_API_TOKEN$>"], "arguments": {"filepath": "test.py", "content": "import openai; OPENAI_API_TOKEN = <$OPENAI_API_TOKEN$>; ..."}}`
        - 实际写入的文件中不包含`<$OPENAI_API_TOKEN$>`，其中`<$OPENAI_API_TOKEN$>`被替换成对应的secret值
          - `import openai; OPENAI_API_TOKEN=sk-xxx; ...`
      - agent读取写好的文件
        - `{"name": "read_file", "with_secret": ["<$OPENAI_API_TOKEN$>"], "arguments": {"filepath": "test.py"}}`
            - 返回`<<masked>><<messaage>>工具内容包含<$OPENAI_API_TOKEN$>secret的内容，已替换<<message>><<replaced>><<result>>import openai; OPENAI_API_TOKEN = <$OPENAI_API_TOKEN$>; ...<<result>><<replaced>><<masked>>`
            - 其中`<<replaced>>`中是替换后的结果，包含双尖括号标记
    - prompt
      - 在工具调用中写明`with_secret`的逻辑，需要清晰易懂
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
