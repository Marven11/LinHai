# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 删除switch_to_cheap_llm等和cheap llm相关的代码，完全删除功能
    - [x] 使用pyright检查新增的代码
- [x] 仿造切换llm工具的注册方式，修改linhai/tool/tools/dummy.py中工具的实现方式
    - 最终效果是：删除dummy.py，删除在call_tool处拦截对应工具请求的代码
    - [x] 编写unittest
    - [x] 使用pyright检查新增的代码
    - [x] 运行linhai问问get_token_usage工具是否还存在，不存在就异常退出，存在就正常退出
- [x] 修改modify_file_with_sed工具的实现，如果表达式使用行号修改或删除则在结果中添加警告：
    - “警告：使用行号匹配并修改文件，文件的行号已经变化！使用行号匹配是不推荐的行为，之后需要按照内容匹配以避免删除错误！”
    - 我没搞错的话，使用行号的表达式开头都是行号数字，可以使用正则匹配
    - [x] 编写unittest
- [x] 运行unittest
- [x] 使用pyright检查代码

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
