# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 删除switch_to_cheap_llm等和cheap llm相关的代码，完全删除功能
    - [ ] 使用pyright检查新增的代码
- [ ] 仿造切换llm工具的注册方式，修改linhai/tool/tools/dummy.py中工具的实现方式
    - 最终效果是：删除dummy.py，删除在call_tool处拦截对应工具请求的代码
    - [ ] 编写unittest
    - [ ] 使用pyright检查新增的代码
    - [ ] 运行linhai问问get_token_usage工具是否还存在，不存在就异常退出，存在就正常退出
- [ ] 运行unittest
- [ ] 使用pyright检查代码

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
