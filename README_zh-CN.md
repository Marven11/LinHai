# 林海漫游

自用编程Agent，设计框架参考Claude Code

![social-preview](./assets/social-preview.jpg)

## Demo

![[demo](https://asciinema.org/a/N6zgQTzjXTNKohXF)](./assets/demo.gif)

## 稳定特性

### 进程控制和远程机器连接

- 动态连接任何bash进程（ssh/sudo bash/docker exec/adb shell）作为机器操控，让agent像操控本机一样操控远程机器
- 支持多跳连接机器: 支持ssh到目标机器并连接sudo bash, 并用同一套工具集（而非复杂的shell命令）操控sudo bash
- 工具集: 比bash+run_in_background更加灵活的进程控制工具集
  - 未退出进程自动转后台
  - 强制输入argv，避开`&&`和pipe的过度使用
  - 后台进程可通过stdio操控，允许使用repl

### TUI

- 流式输出所有token: 思考内容、对话内容、工具调用
- 动态打断Agent输出
- 完善的上下文统计信息和进程管理页面
- 实时展示上下文长度、已消耗token量
- 支持nerd fonts

### 工具

- YOLO in mind: 基于沙箱而非审批的授权哲学
- 完善的软件开发/机器运维工具集: 文件读写、终端操控、进程操控
- MCP: 完全动态化的MCP连接，Agent可以按需连接MCP服务器，避免不使用MCP时带来的Token开销和决策成本
- 沙箱: 文件读写权限规则和进程沙箱 - **动态连接的MCP**也会在沙箱中运行

### 上下文

- 上下文压缩(Context Compacting): 全自动缓存感知上下文压缩 - Agent全自动清理上下文并同时维持缓存率在90%以上
- 上下文组织: 置顶消息+普通消息+通知消息三层结构（类Codex）

### 实用功能

- Planning模式: Agent自主管理状态、待办以及设计文档，不完成所有待办不暂停（启发来自amp/oh my opencode）
- 自动/手动切换llm: 使用`@`语法切换llm, agent调用工具切换llm, 在遇到429/api网络问题时临时切换到fallback llm
- i18n: 中英双语

## 还在糊

- claw模式: Continuous Living Autonomous Worker / 类OpenClaw模式 - 心跳消息、自动更新记忆文件
- telegram远程控制功能
- webshell控制：只是粘上去了而已
- 恢复会话(restore conversation): 没有测试是否可用

## 计划中

- webui
- skills: 只是一堆markdown+总结而已

## 暂时搁置

- MCP(over http): 我们真的需要重新发明REST吗？
- subagent和acp: 不太重要，acp完全可以变成mcp/api

## 安装启动

### (Linux+MacOS+Android+(未测试)Windows) 使用uv从源码安装

```shell
git clone https://github.com/Marven11/LinHai.git
cd LinHai
uv tool install --from . linhai

linhai init
linhai
```

### (准备中) 从pypi安装

```shell
uv tool install linhai
# 使用pipx: pipx install linhai
# 使用系统pip: pip linhai linhai
# 临时使用venv安装: python -m venv /tmp/linhai-venv && . /tmp/linhai-venv/bin/activate && pip install linhai
```

## 配置

```shell
linhai -m '从[config.py](https://github.com/Marven11/LinHai/blob/main/linhai/config.py)开始研究，总结LinHai支持什么配置。如果我之后需要修改配置，帮我修改~/.config/linhai'
```

## 声明

如您通过Github、PYPI等渠道下载本产品则视为同意以下声明

```markdown
本项目产品仅有源代码（以下简称"本产品"）。包括代码文件、配置文档、开发配置在内的一系列文件均属于"本产品"。本项目在中华人民共和国内开发，适用中华人民共和国法律。但本产品不保证在所有司法管辖区均合法，使用者应自行评估并遵守所在地法律。
基于本产品提供任何服务和产品的任何使用者需要向最终用户提供包括本声明在内的本产品，并提供明确的风险提示。因最终用户不知情导致的损失不由本项目开发者负责。
本项目需搭配第三方人工智能模型服务使用。本产品通过频率限制、用量预估、高亮警示等方案保障合理调用服务。本产品保证按上述机制合理调用服务并实时、准确地展示费用相关数据。在非因开发者故意或重大过失的前提下，如用户配置错误、忽视费用指标和预估费用、忽略第三方服务计费规则，则本项目开发者不承担责任。
使用者需避免配置"绕过虚拟化"、"允许执行任意命令"等文档中明确声明应避免修改的功能。本产品仅保证在正确配置时不造成损失。因用户不当配置、启用危险功能、或绕过安全机制导致的损失不由本项目开发者承担。
本产品为以下三类场景设计：个人项目编程、安全靶场测试、简单文档编写，在设计时没有考虑商业项目编程、现实渗透测试等设计外场景。本产品仅对在设计场景下的损失负责。因本产品在设计场景外被恶意攻击造成的损失，和因本产品在设计场景外的不当行为造成的损失不由本项目开发者负责。
本产品集成的测试工具和测试载荷已经通过合理弱化，仅能用于"个人项目漏洞测试"和"渗透靶场攻击测试"两个用途，无法通过商业防火墙、杀毒软件、态势感知等防御机制。在非因开发者故意或重大过失的前提下，如使用者擅自加强、增加测试工具和测试载荷，并用于设计用途之外的场景，则本项目开发者不承担责任。
```