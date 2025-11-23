# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行 git commit，消息参考历史

- [ ] 修改lifecycle系统，支持工具调用失败时的回调
  - 支持获取agent当前的回答
  - 添加unittest测试
- [ ] 添加config项[subagent]，支持设置subagent使用的llm，运行时通过名字寻找llm，如
```toml
[subagent]
default_llm = "deepseek"
```
- [ ] 添加澄清系统
    - 澄清系统是问答形式的TODO列表
    - 如果有澄清没有被解答，则禁止停下等待用户，也禁止使用git
        - 通过检查命令中有没有`git`实现禁止使用git
    - agent持有一个工具：respond_clarification用于回复一个clarification
    - subagent持有一个工具：request_clarification用于添加一个clarification
    - 流程
        - subagent因某些原因被启动，在运行时调用request_clarification等待回答
        - clarification传递给agent，agent收到通知并正常运行
        - agent回复clarification
        - subagent得到回复，选择继续添加clarification或者退出
    - 你可能需要添加一个新的类（放在独立的文件中）来管理所有的clarification
- [ ] 实现一个基于lifecycle事件驱动subagent协作系统
    - 添加一个插件检查
        - 让subagent在工具调用失败时启动，把agent的当前回答传给subagent
        - 让subagent检查agent是否违反了多个工具的调用规则
        - 如果违反了则给agent添加一条澄清：prompt里说xxx, 而你xxx，为什么要xxx?
    - 注意插件需要创建一个task以防止阻塞当前agent
- [ ] 使用https://github.com/darrenburns/textual-autocomplete为当前CLI加上自动补全
  - 你可能需要将输入框从text area改成input组件，并改成回车提交
  - 支持自动获取@和/的补全列表
  - 必须启动linhai测试!
  - 运行所有unittest保证没有破坏性更改

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至emoji总结
