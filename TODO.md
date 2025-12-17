# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] 重构compress_threshold、红绿灯状态等上下文管理工具
  - 逻辑重构
    - 工具分类
      - 消息清理工具: compress_history_range, message_garbage_clean和thanox_history
      - 其他消息管理工具: mark_messages_as_garbage
      - 其他工具: 其余工具，和上下文管理无关
    - 判断红绿灯状态: 仅基于当前message状态
    - 判断上一个回答是否调用了压缩消息的工具: 完全删除
    - 判断最近是否调用过消息清理工具: 仅判断一分钟内有没有调用过**消息清理工具**
    - 判断是否需要拦截消息拦截：只基于红绿灯状态和**最近是否调用过消息清理工具**判断
      - 如果**最近调用过消息清理工具**: 禁止使用消息清理工具，可以使用其他消息管理工具和其他工具
      - 如果**最近没有调用过消息清理工具**且为红灯: 只能调用消息清理工具和其他消息管理工具，禁止调用其他工具
      - 其他状态: 可以调用任何工具
    - 以上判断逻辑均需要编写unittest，测试所有情况！
  - RedStateToolBlockPlugin应该移动到linhai/agent/orchestration.py中，同时其的实现违反CODE_REQUIREMENTS.md，需要修正
  - get_threshold_info应该返回一个typeddict标明每个值的含义，而不是返回一个过长的tuple
  - AgentMessageOrchestration添加appending message的实现应该拆分成一个新的plugin类
  - 当前token长度超出硬限制且**最近没有调用过消息清理工具**则自动调用thanox_history
- [x] 重构prompt.py和SystemMessage，使system prompt的构造结构化
  - 当前主要包含四个部分：总览、各个部分的介绍、注意事项、示例
  - 期望的结果:
    - SystemMessage被注册到group_chat中，全局只有一个SystemMessage
    - SystemMessage接收各个介绍、注意事项、示例，均为字符串，并拼接为正确的结果
    - 存在合适的unittest检测拼接结果
    - SystemMessage提供多个函数支持动态增加注意事项等，虽然现在这些函数没被使用
- [x] 当前agent的message数组有多个称呼: messages, context, history, 全部改成context
  - thanox_history改名成context_thanox, message_garbage_clean改名成context_garbage_clean, compress_history_range改名成compress_context_range
  - AgentMessageOrchestration改名成AgentContextOrchestration
  - 搜索messages和history并思考是否需要改名成context, 大部分都需要更名
- [x] 用户可以通过`/context_garbage_clean`调用context_garbage_clean或者`/context_thanox`调用context_thanox

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
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
- [ ] 为ssh添加terminal工具，实现方式是在trojan.py中维护pty，通过jsonrpc传递pty产生的bytes到主机，主机再通过pyte渲染
- [ ] 解决因为消息过多而无法进行历史压缩的问题
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 