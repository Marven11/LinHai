# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [x] 修改架构，改进CLI样式和性能
  - 现在ReasoningContentWidget的边框是由CSS设置的, MessageWidget各个子component的边框是由Panel设置的
    - 已修改ReasoningContentWidget使用panel以统一
  - MessageWidget在更新完毕被app.py丢弃（不为current_message后）之后没有stop子widget的timer
    - 已为MessageWidget添加stop方法并在app.py中调用
  - ReasoningContentWidget也是，没有在被app.py丢弃（不为current_message后）之后暂停
    - 已为ReasoningContentWidget添加stop方法并在app.py中调用
  - 修改发现的重大性能问题
    - 现在的表现是在只有几条消息时内容正常刷新：每0.1秒刷新一次，在有几百条消息时就变得非常卡顿: 1秒刷新一次
    - 通过停止被丢弃widget的timer来改善性能问题

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加假设颠覆法

