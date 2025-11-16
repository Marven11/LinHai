# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 有些toolcall json block是extract_tool_calls_with_errors可以解析但是linhai/cli/components.py无法解析的
    - 编写测试脚本找出这些block并加入到unittest中，然后修复linhai/cli/components.py和streamjson
- [ ] 使用gettext完成i18n, 按照用户操作系统语言选择对应的语言,默认英文,先完成简体中文和英文的翻译
    - 使用rg搜索所有汉字以找到需要翻译的部分
    - 注释不用改，保持中文


注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
