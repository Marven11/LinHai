# 林海漫游

自用多机器控制编程/渗透Agent，支持Linux/Mac/Android

![social-preview](./assets/social-preview.jpg)

<p align="center">
  <a href="https://pypi.org/project/linhai/"><img src="https://img.shields.io/pypi/v/linhai?style=flat&amp;colorA=222222&amp;colorB=3776AB" alt="PyPI version"></a>
  <a href="https://pypi.org/project/linhai/"><img src="https://img.shields.io/pypi/pyversions/linhai?style=flat&amp;colorA=222222&amp;colorB=3776AB" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-58A6FF?style=flat&amp;colorA=222222" alt="License"></a>
</p>

## Demo

![[demo](https://asciinema.org/a/N6zgQTzjXTNKohXF)](./assets/demo.gif)

## 任何bash进程都是一等公民。

SSH、sudo、docker exec、adb shell --- 连上就是本机。多跳不过是堆叠连接：SSH到服务器，在里面sudo bash，两台都是同一个会话中的一等机器。

- 动态连接任何bash进程（ssh/sudo bash/docker exec/adb shell）作为机器操控
- 多跳连接：ssh到目标机器并连接sudo bash，用同一套工具集操控
- 长时间运行的进程自动后台
- 强制argv避免盲目拼接`&&`
- 后台进程通过stdio保持可控 --- REPL直接能用

## 看到每一个token，随时打断。

思考。对话。工具调用。全部实时流式输出。Agent走偏了？在生成过程中直接打断 --- 不用等一段注定要扔掉的完整回复。

- 流式输出所有token：思考内容、对话内容、工具调用
- 动态打断Agent输出
- 上下文统计、token消耗、进程管理各有独立面板，实时刷新
- Nerd fonts开箱即用

## 沙箱优先，没有审批弹窗。

YOLO式沙箱 --- Agent在规则内工作，而不是绕过规则。没有逐条审批拖慢你的节奏。文件读写、终端操控、进程控制：一套工具集搞定开发和运维。

- 基于沙箱而非审批的授权哲学
- 文件读写权限规则和进程沙箱生效于所有操作
- MCP按需连接、空闲断开，不使用时**零**token开销
- 动态连接的MCP也在沙箱内运行

## 上下文自己压缩自己。

全自动、缓存感知的上下文压缩。Agent自己决定保留什么、压缩什么，缓存命中率保持在**90%**以上 --- 永远不会撞上上下文天花板。

- 全自动缓存感知上下文压缩
- Agent全自动清理上下文并维持缓存率90%以上
- 三层消息结构：置顶、常规、通知（灵感来自Codex）

## Planning模式。LLM切换。中英双语。

Planning模式：Agent自己管理状态、待办和设计文档，每一项不打勾就不停。灵感来自amp和oh-my-opencode。

- Planning模式：自主管理状态、待办和设计文档
- 用`@`语法或工具调用自动/手动切换LLM
- 遇到429/API网络问题自动回退到备用LLM
- 中英双语界面

## 还在糊

CLAW模式 --- Continuous Living Autonomous Worker。心跳消息、自动更新记忆文件，Agent在会话之间保持存活。Telegram远程控制。Webshell控制。恢复会话：没测过。

## 计划中

WebUI。Skills：Agent随取随用的markdown剧本。

## 暂时搁置

MCP over HTTP --- 我们真的需要重新发明REST吗？Subagent和ACP --- 不太重要，ACP完全可以变成MCP/API。

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
