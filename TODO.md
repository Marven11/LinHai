# 等待执行

完成以下所有任务，逐个完成后钩上前面的标记`[ ]`并暂停，不要git add或commit

- [x] load_secrets_from_config应该根据config.toml的相对位置而不是根据当前位置读取secret.toml
  - 需要添加对应的unittest
- [x] 当前http_request工具不支持设置timeout，需要修改
  - 加上一个timeout参数，参数是一个整数，代表timeout的秒数，不需要更加细粒度的参数

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
 
