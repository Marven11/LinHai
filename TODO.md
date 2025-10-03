# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 修改prompt.py中关于多次调用命令的规则，我觉得安全命令之外的几乎所有命令都是安全的，直接删了对应表述，让模型直接执行多个
- [x] 做完上面这个命令就用ps aux | grep linhai检查你的PID然后杀了你自己，我需要重启你
- [x] 修改prompt.py，明确“顺序依赖”的意义：后一个工具是否应该执行依赖前一个工具的结果
    - 如git add失败则不应该运行git commit
    - 如果需要先查询/读取/...再提交/写入/...，或者提交/写入/...的结果依赖前面工具的运行结果，则不要同时调用
    - 如同时修改一个文件的多个地方，如果可以保证修改地方不重复（修改的地方相隔至少5行）的话则可以同时调用
    - 如果同时修改多个文件则可以同时调用
- [x] 修改agent.py，把检查LINHAI.md位置的逻辑等初始化self.messages的逻辑放到create_agent函数中，让agent接收一个参数init_messages
- [x] 在检查LINHAI.md的位置时，不要只检查配置中的LINHAI.md，同时也要检查当前文件夹的LINHAI.md, AGENT.md, CLAUDE.md三个文件是否存在，以及~/.config/linhai/LINHAI.md这个路径
    - [ ] 编写unittest
- [x] 把main.py中配置的默认路径改为~/.config/linhai/config.toml，然后把当前位置的config.toml复制到那里去
- [x] 将linhai/tool/tools/command.py中的execute_command以及调用命令的两个工具都改成async的
- [x] 修改linhai/tool/main.py中的ToolManager，让其在工具函数返回awaitable时await这个awaitable，以同时支持异步和同步函数
    - 这个我写了，你看看实现是否合理
- [x] 为linhai/tool/main.py中的ToolManager编写unittest，测试其是否可以调用异步的工具
- [ ] 添加对应的unittest
- [x] 简化linhai/tool/tools/command.py的实现，尝试不要使用loop.run_in_executor，而是直接await
- [ ] 简化linhai/tests中的文件排布，合并linhai/tests/tool/test_command_async.py和test_tool.py并删除linhai/tests/tool/文件夹
- [x] 在prompt.py中“？”的意思后面加上“！”的意思：用户对你的行为强烈不满，要求你立即完成用户提出的要求，搁置当前的计划，同时根据用户的要求修改你当前的计划
- [x] 让linhai/tool/tools/command.py中的命令输出不仅包含stdout和stderr，也包含status code
- [x] 修改prompt.py，如果任务没有完成就不要暂停
- [ ] 添加`-m`/`--message`选项，支持通过命令行参数手动指定第一条用户命令
- [ ] 为main.py中的命令行参数编写unittest
    - 全面测试所有选项
    - 确保在使用`-m`/`--message`时input函数不会被调用，没有调用时input函数会被调用
- [x] 让test_agent_*.py在消息数量有误时打印每条消息的类型和repr （最多两百字符）
- [x] 运行所有unittest并修复过时的unittest

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）
