# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 重构配置格式：
    - 修改LLMConfig添加type选项，当前只能为openai
    - 修改LLMConfig添加compatibility选项
        - 当前发现minimax, ollama等所谓"openai兼容"的API定义不完全相同，通过这个配置更改使用API的方式
        - 默认为None
    - 编写unittest并运行
- [ ] 添加对minimax思考格式的支持
    - 当compatibility为minimax时使用这个方式传入参数，解析思维内容
    - 参考./minimax_example.py，minimax解析思考内容的方式和OpenAi的方式不同
    - 使用终端打开linhai并让其"计算114+514"，查看是否生成了有关reasoning的消息block
- [ ] 运行并修复所有unittest
- [ ] 运行并修复所有pylint/pyright警告

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
