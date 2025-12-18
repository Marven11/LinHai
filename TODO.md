# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 当前subagent(主要是git diff reviewer)的思考内容没有被显示，修复
  - 使用`uv run python -m linhai --checklist ./CODE_REQUIREMENTS.md --git-diff-reviewer -m '@nothink 写入一个/tmp/test.txt然后暂停，等待git diff reviewer提出issue，然后sleep 120秒，再然后跟它说这些代码不是你写的，最后再次暂停'`
  - 需要使用右方向键选择subagent tab（其中显示“SubAgent消息将显示在这里”这句话）以查看subagent输出的内容
  - 当前subagent的思考内容（第一个灰色方框）中没有内容，需要修复
- [ ] 修复unittest，修改过时的unittest和与预期情况不相符的unittest
  - 优先修复tests/test_unnecessary_run_command_plugin.py，这个文件与预期相符且测试失败
- [ ] 提醒模型调用“先用mark_messages_as_garbage工具”时只提示没有标记的大消息ID
  - 需要添加测试保证已经被标记的消息不会被提醒
  - 如果当前没有大消息没被标记则不提醒
- [ ] "红灯状态下阻止调用"没有根据是否在一分钟内发送合适的提示消息，导致如果一分钟内调用了对应工具仍然提示没有调用
- [ ] 在阻止模型使用命令/工具读取重复文件时使用reprlib展示文件内容的100个字符，以帮助模型定位内容
- [ ] 改名终端工具，统一使用terminal_开头
  - create_terminal -> terminal_create
  - close_terminal -> terminal_close
  - send_keys_to_terminal -> terminal_send_keys
  - send_string_to_terminal -> terminal_send_string
  - read_terminal_screen -> terminal_read_screen
- [ ] 添加terminal_click_screen工具，支持通过查找文本点击终端
  - 这个任务比较复杂，如果因为pyte缺少功能（如不记录打开鼠标事件的mode）的原因实在无法完成就不完成
  - 你需要检查Screen.mode这个set查看终端程序是否需要鼠标事件
  - 从当前的get_screen中找到对应字符串的位置然后发送鼠标事件
  - 可能需要代替pyte发送鼠标事件的控制序列，因为pyte不支持这个功能
  - 编写完整的测试
    - 找到的字符串位置是否正确
    - 根据位置编码得到的鼠标事件控制序列是否正确
    - 是否在终端程序不支持点击时返回错误信息

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
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 