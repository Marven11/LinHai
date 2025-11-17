# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 写一个新插件
    - 有时agent会根据prompt.py中的示例错误的输出`**tool**`
    - 当目前是agent生成的第一个回复且有一行的开头是`**tool**`时打断agent，并提示不要输出工具调用的内容
- [x] 修改CLI，增加标签页功能
    - 在https://textual.textualize.io/找到对应widget的文档
    - 设计两个标签页：
        - agent对话标签页：保持和当前界面相同，有agent对话记录和文本框
        - “笔记”标签页：markdown分点展示当前agent留下的笔记
            - 当前只有一条笔记: `TODO`
    - 创建终端测试
- [x] 将CLI的滚动条改成灰色，并减小长度
- [ ] 让底部的Token用量条永远显示，不仅仅显示在agent对话tab中

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，必须创建terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
