# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要 git add 或 commit

- [x] 当前的token用量的传递问题很大
  - app.py注册对应队列，在watch_token_usage_queue接收token usage并传给token manger - 改成让token manager自己注册并接收，清理对应代码
  - 大量代码使用agent.last_token_usage读取token用量
    - 完全清理last_token_usage的使用，清理完后搜索last_token_usage检查
    - 全部改为使用token manager

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

- [ ] 修改显式缓存价格的配置
  - 我们发现每个LLM的显式缓存价格都不同
    - Claude Opus 4.6: 未缓存输入token: `$5`/MTokens; 缓存命中输入token:  `$0.5`/MTokens; 缓存写入输入token: `$6.25`/MTokens
    - qwen3.5 plus: 未缓存输入token: 0.8元/MTokens; 缓存命中输入token:  0.08元/MTokens; 缓存写入输入token: 元/MTokens
  - 修改配置
    - 去除use_explicit_cache，为llm添加可选的explicit_cache配置项
      - 包含三个配置项：enable（如果有这个配置项则必填）、缓存写入的价格相对于未缓存为多少、缓存命中相对于未缓存为多少
    - 去除LanguageModel的use_explicit_cache函数，加上get_explicit_cache_info函数，在未开启explicit_cache时返回None，开启时返回配置的价格信息
    - 让message.py使用get_explicit_cache_info而不是预先配置的价格
    - 编写对应测试，清理对应代码
- [ ] 添加初始化配置的功能
  - 用户运行python -m linhai init可以打开初始化TUI页面，可以设置第一个llm的openai的base_url, api_key等
  - 参考https://github.com/Textualize/textual/blob/main/examples/calculator.py
- [ ] 我们需要用更加简洁的设计复刻openclaw的核心功能
  - openclaw的核心功能：
    - 从各个IM接收用户消息并转发给agent, agent可以通过id等回应用户
    - agent可以暂停等待输入，但是暂停后每隔一段时间就会收到一条心跳消息而被打断暂停
    - 其余功能和常见的coding agent(linhai/claude code/ ...)相同

# 注意

- 在终端刚刚启动 linhai 时 TUI 焦点锁定在 tab 区域，需要按下 tab 键选择对话区域才能使用 pageup/pagedown 翻页，查看最新回答
- 总是开启的插件默认在lifecycle.py中注册，视情况开启的插件在create.py中注册

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到 agent 上下文的好坏，从而直接影响 agent 性能
./linhai/group_chat.py - group chat 的设计，用来连接各个单例，需要先检查其中的文档注释再使用 GroupChat 类
