# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 将exit_agent工具改名为exit_app工具，描述改为退出
- [ ] 除了主LLM之外，现在配置文件只支持配置一个额外的cheap LLM，将配置格式改成接受多个llm（在配置中是一个列表），每个llm都有自己的名字(name属性)，创建agent时将llm的列表传给agent对象，默认选择第一个llm
    - [ ] 编写对应的unittest
- 做完上一个任务暂停
- [ ] 仿造cli_ui.py添加exit_app工具的方式，让agent类在启动时添加“切换llm”工具和“当前llm”工具
    - 切换llm工具描述根据当前有的llm自动生成
    - 如果llm名字不存在，则列出所有llm

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
