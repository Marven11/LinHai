# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 重构agent_plugin.py为主的agent plugin系统和lifecycle系统
    - [ ] lifecycle类初始化时
        - 获得group chat并注册自己
        - 初始化各个默认插件（列表）并保存在self中
    - [ ] plugin在初始化时获得group chat类
    - [ ] agent在传递给plugin时不再通过lifecycle的参数传递
        - [ ] 删除lifecycle调用callback时传递的agent参数
        - [ ] 删除plugin调用callback时传递的agent参数
        - [ ] plugin在运行时通过group chat获得agent
    - [ ] 运行并修复unittest
- [ ] 将delete_message_by_uuid改为erase_message_by_uuid
    - 逻辑由从直接删除改为在原位置插入一条runtime message: 本条UUID为{UUID}的消息已被擦除
    - 改完用rg看一下有没有其他提到delete_message_by_uuid的地方，一起改了
    - 运行unittest并修复
- [ ] 现在工具返回了tool error message时ToolManager也会发送“工具调用成功”的消息，应该发送“工具调用失败”的消息
    - 编写unittest
- [ ] 给ToolCallMessage加上一个assert_success参数
    - 默认为True
    - 注释：假设工具调用成功，在工具调用失败时中止当前消息的其他工具调用
    - 修改agent.py
        - 在call_tool中如果需要中止则返回False
            - tool result是ToolErrorMessage
            - 出现Exception
    - 编写unittest
        - [ ] 从llm输出中解析assert_success参数，没有时为True
- [ ] 修复pylint, pyright的警告，每修复一个文件就重新运行unittest保证没有修坏

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
