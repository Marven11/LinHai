# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 在prompt.py中修改prompt, 让agent注意在压缩历史时输出的格式不要和调用工具时的输出一样只输出计划，一定要包含压缩历史时的那几点
- [ ] 修改agent.py，把检查LINHAI.md位置的逻辑等初始化self.messages的逻辑放到create_agent函数中，让agent接收一个参数init_messages
- [ ] 在检查LINHAI.md的位置时，不要只检查配置中的LINHAI.md，同时也要检查当前文件夹的LINHAI.md, AGENT.md, CLAUDE.md三个文件是否存在，以及~/.config/linhai/LINHAI.md这个路径
- [ ] 把main.py中配置的默认路径改为~/.config/linhai/config.toml，然后把当前位置的config.toml复制到那里去
- [ ] 将linhai/tool/tools/command.py中的execute_command以及调用命令的两个工具都改成async的
- [ ] 修改linhai/tool/main.py中的ToolManager，让其在工具函数返回awaitable时await这个awaitable，以同时支持异步和同步函数
    - 这个我写了，你看看实现是否合理
- [ ] 为linhai/tool/main.py中的ToolManager编写unittest，测试其是否可以调用异步的工具
- [ ] 添加对应的unittest
- [ ] 简化linhai/tool/tools/command.py的实现，尝试不要使用loop.run_in_executor，而是直接await
- [ ] 简化linhai/tests中的文件排布，合并linhai/tests/tool/test_command_async.py和test_tool.py并删除linhai/tests/tool/文件夹
- [ ] 在prompt.py中“？”的意思后面加上“！”的意思：用户对你的行为强烈不满，要求你立即完成用户提出的要求，搁置当前的计划，同时根据用户的要求修改你当前的计划
- [ ] 运行所有unittest并修复过时的unittest

注意：一定记得git commit|参考历史commit|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）
