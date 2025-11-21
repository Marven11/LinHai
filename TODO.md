# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行 git commit，消息参考历史

- [ ] 修改思考消息时的显示样式，如果一行超出了当前内容则用省略号省略，不要换行
  - 让普通消息按字符换行，让思考消息不换行
  - 你需要为思考消息创建一个新的 widget，顺便简化当前消息 widget 的实现
- [ ] 增强CLI中使用的Markdown Lexer
    - 抄/Users/cube/Code/Python/LinHai/.venv/lib/python3.13/site-packages/pygments/lexers/markup.py
    - 添加对四个或更多反引号的支持
    - 编写测试 (Update TODO)

注意：一定记得参考历史 commit|git commit|勾上 TODO - 一定在你的任务规划中显式规划读取历史 commit|git commit|勾上 TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件，并且需要至少给定 30 秒的等待时间

# 暂时搁置

- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至emoji总结
