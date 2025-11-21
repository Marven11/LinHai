# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行 git commit，消息参考历史

- [ ] 使用https://github.com/darrenburns/textual-autocomplete为当前CLI加上自动补全
  - 你可能需要将输入框从text area改成input组件
  - 支持自动获取@和/的补全列表
  - 必须启动linhai测试!
  - 运行所有unittest保证没有破坏性更改

注意：一定记得参考历史 commit|git commit|勾上 TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至emoji总结
