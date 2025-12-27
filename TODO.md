# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] delete trigger_after_working
- [?] 在lifecycle中添加before_agent_loop这个lifecycle hook，在Agent.run函数中的`while True:`前调用
  - [ ] 让PromptFastAgentPlugin使用before_agent_loop而不是before_message_generation添加“你现在是xxx”的prompt
- [ ] 修改appending_message的设计
  - appending_message支持排序：在添加时支持指定appending_message的排序方式
  - 每个appending_message除了有source, message之外增加一个排序权重,起名格式为xxx_value,必须指定，不能默认为0
    - 好好想想这个权重应该叫什么
    - 需要定义TypedDict保存每个appending_message的source, message等，作为self.appending_messages的value
  - 在get_messages中根据这个value排序
  - update_appending_message需要添加一个参数指定这个权重

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 让Agent在调用工具前提前规划任务
  - 任务规划格式
    - 输出在```json toolcall前的一段嵌套无序列表，使用`[ ]`和`[x]`标记完成的和未完成的任务
    - 例子在下方
  - 配置
    - 可以在配置中通过`[agent]`中的配置项开关，默认关闭
  - 文件架构
    - 所有实现放在linhai/agent/planning.py中
  - 插件
    - 任务规划prompt添加插件: hook before_agent_loop，添加介绍任务规划的prompt
- [ ] 修改_build_threshold_message使其提示以下信息，使用以下格式
  - `当前为x灯状态, 上下文占用量为xx%, 当前有x条大消息, 一分钟内有/没有调用过..., 建议: ...`
  - 在黄灯状态: 提示避免读取文件，直接开始修改文件，只在消息多于5条时提示“应该调用context_garbage_clean”
  - 如果一分钟内调用过消息清理工具，无论是否红灯，都不应该提示应该调用消息清理工具
  - 在消息清理工具方面
    - if 一分钟内调用过消息清理工具：不应该调用消息清理工具
    - elif 红灯: 立即...
    - elif 黄灯且消息多于5条: 应该调用context_garbage_clean工具
  - 在其他方面
    - if 一分钟内调用过消息清理工具: 不要担心消息限制，继续工作，在这一分钟过去后runtime会另行通知
    - elif 红灯: 立即暂停当前任务
    - elif 黄灯: 应该避免读取文件，立即开始修改
    - else: assert 绿灯, 不要担心消息限制，立即工作

## 任务规划例子

- [ ] 探索代码
  - [x] 列出当前文件夹
  - [x] 搜索xxx
  - [ ] 根据当前文件夹的内容继续探索其中的内容
- [ ] 开始编写代码
  - [ ] 完成xxx
  - [ ] 完成unittest

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
- [ ] 完全删除should_block_command_simple，让UnnecessaryRunCommandPlugin只拦截已经读取文件的情况
  - [ ] 同时测试以下命令是否会被正常拦截: `tail -10 xxx.txt`, `head -10 xxx.txt`，如果没有被拦截则修复并添加对应unittest
- [ ] UnnecessaryRunCommandPlugin没有拦截awk和rg，修复并添加对应的unittest
- [ ] UnnecessaryRunCommandPlugin, UnnecessarySedReadPlugin, DuplicateFileReadPlugin应只在当前在master_host上时拦截
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 
