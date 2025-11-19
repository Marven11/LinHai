# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [x] 把多余的linhai/agent/plugins/prevent_tool_output.py合并到linhai/agent/plugin.py，并清理多余的文件夹
    - [x] 运行unittest确认没有破坏性调整
- [ ] 修复错误的unittest, to_json不可能是异步函数！
- [ ] 清理unittest中的垃圾消息
    - `DeprecationWarning: It is deprecated to return a value that is not None from a test case (<bound method TestCLITabs.test_tabs_display of <tests.test_cli_tabs.TestCLITabs testMethod=test_tabs_display>>)`
    - `/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/unittest/case.py:606: RuntimeWarning: coroutine 'TestCLITabs.test_tabs_display' was never awaited`
- [ ] 调整NormalContentWidget等的边框颜色，使其和nord主题更加搭配
    - [ ] agent思考使用secondary
    - [ ] agent回答使用primary
    - [ ] 工具调用使用调整后的紫色
    - [ ] 用户消息使用调整后的绿色
    - [ ] 运行linhai确认可以成功启动

注意：一定记得参考历史commit|git commit|勾上TODO|历史压缩
    - 一定在你的任务规划中显式规划读取历史commit|git commit|勾上TODO|历史压缩
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，必须创建terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
