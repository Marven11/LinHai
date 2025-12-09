# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [ ] 在context tab中显示所有的appending message
- [ ] 添加插件禁止无用的run_command
  - 原因：
    - LLM经常在读取文件之后仍然使用额外的工具查看文件内容
    - 这是因为当前任务较难，相较于仔细思考如何编写代码来说，再次确认代码内容要“简单得多”，这是在拖延
  - 目标：完全阻止LLM通过重复读取文件拖延，需要设计良好的prompt
  - 完全禁止直接使用sed命令查看单个文件，提示：“禁止直接使用sed命令查看文件！”
  - 禁止使用这些工具查看已经读取了的文件: grep, head, tail, cat, sed
  - 例外：使用`|`或者`>`重定向，有时LLM需要提取文件的部分内容。
  - 使用bashlex实现
    - 找到所有不在PipelineNode中且不含RedirectNode的CommandNode
    - 提取其中的命令判断是否需要拦截

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 研究多subagent协作
  - 需要有两个甚至多个subagent讨论出一个方案再提供给agent修改
- [ ] terminal tab
- [ ] 添加假设颠覆法

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
