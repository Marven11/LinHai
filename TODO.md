# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并进行git commit，消息参考历史

每完成一个任务就压缩历史一次（因为完成之后历史消息几乎都是无用的）

- [ ] 使用pyright查看cli_ui.py中的类型错误，应该要避免使用self.content
- [ ] 修改linhai/cli_ui.py，如果MessageWidget数量大于1000则删除前面的以优化性能
- [ ] 修改linhai/tool/main.py的逻辑，不仅提供行数等信息，还提供内容的预览
    - 使用reprlib压缩到500字符
- [ ] 修改linhai/prompt.py中的示例，修改其中的任务规划格式为markdown分级无序列表+方框
- [ ] 运行并修复unittest

注意：一定记得git commit|参考历史commit|历史压缩|勾上TODO
注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：运行linhai时，linhai不会使用STDIO输出消息，更不会在结束时自动退出！你应该在message中告诉linhai使用工具写文件并退出！

# 暂时搁置

- [ ] 研究subagent集成
