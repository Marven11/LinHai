# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行 git commit，消息参考历史

- [x] 重构subagent系统
  - 支持在配置中开关subagent，默认打开
  - 在subagent被开启时才注册相关的plugin和subagentmanager
    - 将plugin的实现和注册plugin的相关代码等都移动到linhai/subagent中
      - 确保几乎所有会被选项关闭的逻辑都在linhai/subagent中
  - 添加以上功能的unittest

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
