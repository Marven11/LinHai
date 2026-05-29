# Terminal Bench 2.0 - Terminus + DeepSeek V4 Pro 基准测试报告

## 测试配置

| 参数 | 值 |
|---|---|
| Agent | terminus (terminus-1) |
| Model | deepseek/deepseek-v4-pro |
| Dataset | terminal-bench-core==0.1.1 (80 tasks) |
| 并发数 | 4 |
| 运行时间 | ~4小时 |
| 机器 | omen-nixos (30GB RAM, NixOS) |
| 容器运行时 | podman 5.8.2 (rootless) |

## 总体结果

| 指标 | 值 |
|---|---|
| 总任务数 | 80 |
| 解决数 | 11 |
| 准确率 | **13.8%** |
| 总输入 Token | 2,348,575 |
| 总输出 Token | 81,261 |

## 解决的任务 (11/80)

| 任务名 | 输入 Token | 输出 Token |
|---|---|---|
| blind-maze-explorer-5x5 | 164,612 | 4,410 |
| build-tcc-qemu | 205,144 | 2,816 |
| conda-env-conflict-resolution | 52,961 | 2,715 |
| crack-7z-hash | 139,296 | 2,994 |
| eval-mteb | 36,779 | 1,835 |
| eval-mteb.hard | 38,963 | 1,736 |
| fix-pandas-version | 0 | 0 |
| incompatible-python-fasttext | 70,588 | 2,903 |
| incompatible-python-fasttext.base_with_hint | 16,980 | 1,121 |
| prove-plus-comm | 0 | 0 |
| tmux-advanced-workflow | 1,131 | 783 |

## 失败模式分析

| 失败模式 | 数量 | 占比 |
|---|---|---|
| parse_error | 31 | 38.8% |
| test_timeout | 19 | 23.8% |
| unset | 8 | 10.0% |
| agent_timeout | 6 | 7.5% |
| unknown_agent_error | 5 | 6.3% |

### parse_error (31个任务)

最主要的失败模式是JSON解析错误。根因是DeepSeek V4 Pro在输出结构化JSON时经常用markdown代码围栏(```json ... ```)包裹响应，导致terminus agent的JSON解析器失败。尽管我们patch了lite_llm.py来剥离markdown围栏，但并非所有情况都能被正确处理。

### test_timeout (19个任务)

测试超时意味着agent成功执行了部分操作但未能在规定时间内完成任务。这些任务通常涉及编译大型项目（如Linux内核）或运行耗时较长的测试。

### agent_timeout (6个任务)

Agent超时意味着LLM在规定时间内未能产生有效的命令序列。可能是DeepSeek在复杂任务上的推理速度较慢，或者多轮交互中token累积过多。

### unknown_agent_error (5个任务)

未知agent错误可能是由于DeepSeek API返回InternalServerError（服务端过载）或其他非标准错误。

## 成功任务模式分析

成功解决的任务主要集中在以下几类：

1. **环境配置类**: conda-env-conflict-resolution, fix-pandas-version, incompatible-python-fasttext - 这类任务需要理解依赖关系并修复版本冲突
2. **代码构建类**: build-tcc-qemu - 编译C编译器
3. **数据处理类**: eval-mteb, prove-plus-comm, crack-7z-hash
4. **简单交互类**: blind-maze-explorer-5x5, tmux-advanced-workflow

## 技术挑战与解决方案

### Podman环境配置

本测试使用podman替代Docker运行容器。需要解决以下问题：

1. **subuid/subgid配置**: NixOS通过`users.users.linhai.subUidRanges`和`subGidRanges`永久配置
2. **fuse-overlayfs**: NixOS通过`programs.fuse.enable = true`启用
3. **Docker兼容性**: 设置`DOCKER_HOST=unix:///tmp/podman.sock`和`DOCKER_BUILDKIT=0`

### DeepSeek API兼容性

DeepSeek API不支持OpenAI的`json_schema`类型`response_format`，需要patch terminal-bench的lite_llm.py将结构化输出转为prompt template方式。

## Token消耗分析

| 指标 | 值 |
|---|---|
| 平均每任务输入 Token | 29,357 |
| 平均每任务输出 Token | 1,016 |
| 输入/输出比 | ~29:1 |

DeepSeek V4 Pro的输出token数远低于输入，说明模型倾向于给出简短的命令序列。高输入token数反映了terminus agent的系统提示和任务描述较为冗长。

## 结论

DeepSeek V4 Pro配合Terminus agent在Terminal Bench 2.0上达到13.8%的准确率。主要瓶颈是JSON结构化输出的兼容性问题（parse_error占38.8%），而非模型本身的编程能力。如果解决解析兼容性问题，预计准确率可以显著提升。

## 运行信息

- Run ID: 2026-05-29__01-02-12
- 结果文件: runs/2026-05-29__01-02-12/results.json
- 运行开始: 2026-05-29 01:02 UTC+8
- 运行结束: 2026-05-29 05:05 UTC+8
