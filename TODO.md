# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] 重构subagent配置和--git-diff-reviewer选项等
  - 当前: 只要指定--checklist就会在暂停时启动git diff reviewer，这不合理
  - 重新设计:
    - git diff reviewer和violation checker默认关闭
    - subagent配置
      - 仅包含enable和default_llm选项，不控制对应subagent类型的开启和关闭
    - --checklist选项
      - 在上下文中加入checklist文件的内容
    - --git-diff-reviewer选项
      - 提供此选项时注册git diff reviewer插件: GitDiffReviewPlugin
    - --violation-checker选项
      - 提供此选项时注册violation checker插件
- [x] 之前几个commit没有修改unittest，现在有大量过时unittest失败
  - 状态：从最初的81个错误减少到0个错误，所有504个测试通过

# 暂时搁置

- [ ] terminal tab
- [ ] 添加假设颠覆法

# 注意

- 在终端刚刚启动linhai时TUI焦点锁定在tab区域，需要按下tab键选择对话区域才能使用pageup/pagedown翻页，查看最新回答，

# 资源

./PROJECT.md - 稍微有些简陋的文档，说明了当前项目的技术亮点
./CODE_REQUIREMENTS.md - 代码风格要求，编写时要注意
./MESSAGE_DESIGN.md - 消息设计，直接关系到agent上下文的好坏，从而直接影响agent性能
./linhai/group_chat.py - group chat的设计，用来连接各个单例，需要先检查其中的文档注释再使用GroupChat类
 
