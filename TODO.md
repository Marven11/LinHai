# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 研究如何读取互联网上的文章：
    - 我们到目标是添加一个工具，用来读取互联网上的文章，并转为markdown让agent读取
    - 写一个示例，使用selenium访问网站，保存对应的HTML到临时.html文件，然后使用这条pandoc命令转成markdown
        - `pandoc {}.html -o a.md --to=markdown-markdown_in_html_blocks-fenced_divs-native_divs`
    - 然后输出报告ANALYSIS_FETCH_ARTICLE_MARKDOWN.md，介绍过程和效果
- [x] 用black格式化 - 已完成，代码无需更改


注意：你没法直接使用你修改/新增的功能（因为你没有重启）

# 暂时搁置

- [ ] 调整MCP对接命名规范（避免双下划线）
- [ ] 改进文件编辑tool的安全性处理（允许渗透代码但警告）
- [ ] 添加微信公众号文章读取功能
- [ ] 让所有Message都支持序列化和反序列化，方便保存到本地文件中，不要使用pickle而是使用安全的序列化方式
- [ ] 处理代码中的prompt injection风险
- [ ] 研究subagent集成
- [ ] 实现插件系统（运行时启用、修改prompt、处理token限制）