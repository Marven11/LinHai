# 等待执行

依次完成以下任务，逐个完成后钩上前面的标记`[ ]`并暂停

- [ ] 将send_string_to_terminal的with_enter改成必须参数
  - 记得同时修改unittest
- [ ] 修改“收到来自SubAgent的澄清问题...”为“收到来自SubAgent(@xxx)的澄清问题，ID为yyy....”，其中xxx是SubAgent的ID, yyy为澄清问题的ID
  - 让Agent明白SubAgent的ID是什么，澄清问题的ID又是什么
- [ ] 将每类subagent的启动、运行等都独立到单独的文件中，而不是像现在这样
  - 现在启动subagent的逻辑散落在plugin中，运行
  - 你需要重构代码，为每类subagent单独开一个文件（甚至文件夹），包含插件、启动逻辑等，只有完全通用的逻辑才能放在外面
  - 最终的效果是
    - 只需要指定类型等少量信息就可以启动一个subagent
    - 添加一个subagent几乎不需要修改公共代码
  - 顺便把prompt.py中的subagent prompt也移动一下

注意：你没法直接使用你修改/新增的功能（因为你没有重启）
注意：增加新功能需要添加unittest，修改功能需要修改对应的unittest
注意：运行 linhai 时，必须创建 terminal 运行 linhai，因为 linhai 是 TUI 软件

# 暂时搁置

- [ ] GitDiffReviewPlugin的_get_new_files_content没有处理新增文件夹的情况
  - 尊重.gitignore: 可能需要通过git查看新文件内容以尊重.gitignore，次解为使用第三方库解析.gitignore, 不要手动解析！
- [ ] 修改架构，现在的Answer只能被打断生成，但是不能被截断
  - 我们需要添加一个架构让Answer支持截断，相当于提前帮LLM结束输出
  - 作用：有时候LLM会调用大量工具，但是我们希望让其在调用5个工具之后停下来，我们可以通过提前截断手动停下LLM输出
  - 和打断的区别：
    - 打断是暂停输出，本次输出失败，其中的工具调用等信息都不会被处理
    - 提前结束是暂停输出，流程继续，就像LLM正常停止输出一样
- [ ] 支持配置每类subagent的开关
- [ ] 让compress_history_range在启动时显示一个ui_log，报告当前共有几条消息
- [ ] 重构CLI的底栏
  - 应该抽象为一个Widget自己刷新自己
  - 这个Widget每0.5秒刷新一次，自动获取当前的message量
  - 每个Answer的token用量等信息由CLIApp传给这个Widget
- [ ] 给一个配置让CLI底栏使用nerd font中的icon
  - 默认关闭，用户可以通过`[cli]`中的配置项打开
  - https://www.nerdfonts.com/cheat-sheet
    - 图标\uf49b代表缓存
    - 图标\uf27a代表消息
    - 图标\uf063代表in
    - 图标\uf062代表out
- [ ] 有时agent会误用`json`而非`json toolcall`的代码块调用，写一个插件在此时警告Agent
  - 检测`json`代码块，看看是否可以获得正确的工具调用
  - 如果agent确实将工具调用放在json而非json toolcall中，警告：
    - 警告内容包括工具的名字，不包括工具的参数（太长了）
    - 弹一条UI消息
  - 你需要修改extract_tool_calls_with_errors添加参数，以重用代码
- [ ] OpenAiAnswer的estimated_usage会在哪里被用到？没有用则删除
- [ ] 添加假设颠覆法
- [ ] 添加响应式 SubAgent
  - 避免拍马屁
  - 避免在工具调用未结束时就报告“完成”
  - 避免同时读取并写入文件
  - 避免使用无序分点甚至 emoji 总结
