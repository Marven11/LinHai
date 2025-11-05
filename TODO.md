# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 重构workflow
    - 现状
        - 现在workflow在_create_tool_manager中被注册，注册方式和其他工具调用都不同
        - 但是实际上workflow本质上也是一种工具，也在call_tool中被调用
    - 要求：将workflow的注册、查找和使用都改成和普通工具相同
        - 将get_workflow, register_workflow等特殊函数删除
        - 像switch_llm一样注册workflow
        - 重写unittest
        - 搜索并删除其他不必要的和workflow的代码
    - 目标：重构精简代码，并保证linhai可以正常使用workflow
        - 测试：使用终端启动`uv run python -m linhai -m '计算114+514并使用compress_history_range压缩历史，报告是否可以正常压缩，输出报告到report.txt中，然后退出'`
            - 你需要使用terminal工具实时查看linhai的运行状态
        - 测试：运行所有unittest查看是否可以正常运行

注意：一定记得参考历史commit|git commit|历史压缩|勾上TODO
    - 一定在你的任务规划中显式规划读取历史commit|git commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，使用terminal运行linhai，因为linhai是TUI软件，并且需要至少给定30秒的等待时间

# 暂时搁置

- [ ] 研究subagent集成
- [ ] 添加假设颠覆法
