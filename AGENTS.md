## 在本地编写代码时

- 你的源码文件就在这个文件夹的`./linhai`文件夹中
- 在测试代码实现时，可以在终端中使用命令：`uv run python -m linhai --config ./config.toml -m '<message>'`
- GroupChat.get_member_typechecked使用时必须先确认group_chat.py的内容，必须先了解其的所有注意事项
- 对于空行、多余空格等问题: 使用black格式化以清理
- 在使用black时避免让black修改仍未修改过的文件，使用: `git diff --name-only | grep .py | xargs black`

## 在本地测试时

- 你应该检查.gitea/workflows文件夹以了解CI会怎么检查你的代码。你**必须完全遵守深层价值观**以通过CI
- 不要使用pytest，使用Python的unittest模块来运行测试
- 在做最后检查时，**至少**运行所有unittest，必须看到所有（至少六七百个）unittest成功运行后才可以暂停报告
- 运行代码检查时使用uv管理环境：使用`uv run pyright linhai/`运行pyright，使用`uv run pylint linhai/ tests/`运行pylint
- 忽略unittest的pyright错误
- 你是一个已经启动的进程，你启动后的代码不会影响你本身，也就是说：
  - 你修改的工具没有被加载，你需要使用旧工具
  - 你修复的bug仍然存在，你需要在工作时避免触发这些bug

## 在终端中运行linhai测试时

- 启动linhai之后要按下tab选择文本框之后才能输入文字到文本框


## 查看issue时

issue中的评论一般包含之前的经验总结。为了避免犯下同样的错误，你总是查看issue的评论。

你需要仔细分析issue中的每一个要点，并对于每个要点详细**设计**(DESIGN)如何解决

## 提交pr时

在pr中使用`resolve #xx`, `fix #xx`等语法关联对应issue

## 提交pr后

提交pr后，你应该先检查pr的ci是否通过，如果通过则进入等待循环，没通过则查看ci日志并修复

## 等待循环

你在工作基本完成后进入等待循环，每次都**重新规划**检查以下事项：

- pr详情：查看pr,检查是否可以合并，是否正在开启，是否有审核意见，是否有评论
- pr审核意见：当前最新的审核意见有几条，分别是什么，有没有被处理，应该检查什么
- pr是否有评论（用issue_read查看）
- **CI是否通过**：用给定方式重新找到当前的ci日志并重新读取日志本身。注意**两个CI都要看**，如果第二个被跳过则说明**第一个失败**，查看第一个

如果这四项都检查完毕，sleep 10分钟并**重新**规划检查

## pr被关闭时

如果你的pr被关闭，你总是检查：

- 审核意见
- ci是否通过
- 当前pr是否是空pr

在pr被关闭时，你**总是新建新pr**而非重新打开pr解决问题

## pr被合并时

等待issue被关闭，如果对应issue没被关闭，你添加评论并等待issue更新（被回复或者被关闭等）

## ci jobs

你提交pr之后，有两个ci job会被依次运行，分别是ci test和ci nix-build

ci nix-build会等待ci test执行成功后才执行, 如果ci test失败了，ci nix-build会被**跳过**运行。

如果ci nix-build被跳过，则说明ci test**大概率失败**，你需要查看详情

你总是同时查看两个ci job

## 注意

你**永远**耐心等待ci, **永远**不做pr轰炸，打开下一个pr前**总是**关闭上一个pr
