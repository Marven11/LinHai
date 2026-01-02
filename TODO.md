# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 当前assert_success选项无用
  - 问题: 带上assert_success选项调用两个工具读取一个不存在的文件和一个存在的文件，正常来说指定了assert_success的话即使一个工具失败下一个工具也会执行，而不是被跳过
    - 测试: 在终端中运行linhai: `uv run python -m linhai -m '@nothink 带上assert_success=False选项先后调用两个工具读取一个不存在的文件和一个存在的文件，报告两个工具的执行结果，是成功读取，读取失败还是被跳过，报告到/tmp/report.txt然后退出'`
    - 你没有重启，修复代码后依然会遇到这个问题
  - 分析assert_success的应有行为
    - assert_success类似try-catch机制，当设置为True时工具调用出错会打断后面的工具调用，就像函数调用抛出错误一样，而assert_success为False时工具调用出错不会打断后面的工具调用，就像用try-catch捕获了错误一样
  - 修复问题
    - 查看当前调用工具的逻辑，我记得好像是有一个bool记录是否需要跳过工具，需要修改这个bool的设置逻辑
  - 编写/修改unittest确认问题
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

# 暂时搁置

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
 
