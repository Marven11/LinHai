# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

- [x] 我刚刚重构了llm.py，查看上一个commit并修正unittest
- [x] 修正unittest
- [ ] 重构watch_output_queue，拆成四个task分别监听自己的queue, 拆分超大if语句
- [ ] 继续重构llm.py的answer_stream
    - 不要让OpenAIAnswer通过持有OpenAi实例更新OpenAi的previous...
    - 让OpenAi实例传入一个callback，OpenAiAnswer调用Callback实现更新
- [ ] 修正unittest

注意：一定记得参考历史commit|git commit|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，必须创建terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 添加假设颠覆法
