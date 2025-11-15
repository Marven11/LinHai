# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 参考/home/cube/Code/Python/StreamJson改进现在的CLI界面Agent消息：实现流式显示每个键值对
    - 你需要先运行stream json中的示例看看它能输出什么
    - 你需要将stream json的实现直接复制到当前项目
    - 现在的CLI会在消息中直接显示原始的toolcall的JSON字符
    - 改进成在消息block中嵌套显示键值对：
        - 一个两列的表格，左边显示键，右边显示值
        - 表格内容必须流式填充！
        - 表格必须美观，带有合适的边框，嵌套在message框中
    - 修改前后运行linhai让其计算114514+1919810观察CLI是否修改成功
- [ ] 移动linhai/tests的测试到tests/中

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
