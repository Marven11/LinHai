# LinHai

A Multi-Machine Control Coding/Hacking Agent running on Mac/Linux/Android.

[中文文档](./README_zh-CN.md)

![social-preview](./assets/social-preview.jpg)

## Demo

![[demo](https://asciinema.org/a/N6zgQTzjXTNKohXF)](./assets/demo.gif)

## Stable Features

### Process Control and Remote Machine Connection

- Dynamically connect any bash process (ssh/sudo bash/docker exec/adb shell) as a machine, allowing the agent to control remote machines as if local
- Multi-hop machine connections: ssh to a target machine and connect sudo bash, controlling it with the same toolset (instead of complex shell commands)
- Toolset: process control toolkit more flexible than bash+run_in_background
  - Long-running processes automatically background
  - Force argv input to avoid excessive `&&` and pipe usage
  - Background processes controllable via stdio, supporting REPLs

### TUI

- Stream all tokens: thinking content, conversation content, tool calls
- Dynamically interrupt Agent output
- Comprehensive context statistics and process management pages
- Real-time display of context length and token consumption
- Nerd fonts support

### Tools

- YOLO in mind: sandbox-based authorization philosophy instead of approval
- Comprehensive software development and machine operations toolset: file read/write, terminal control, process control
- MCP: Fully dynamic MCP connections - Agent connects to MCP servers on demand, avoiding token overhead and decision-making costs when MCP is not in use
- Sandbox: file read/write permission rules and process sandbox - **dynamically connected MCP** also runs within the sandbox

### Context

- Context Compacting: fully automatic cache-aware context compression - Agent automatically cleans context while maintaining cache hit rate above 90%
- Context organization: pinned messages + regular messages + notification messages (Codex-like)

### Practical Features

- Planning mode: Agent autonomously manages status, todo, and design documents; does not pause until all todos are completed (inspired by amp/oh my opencode)
- Auto/manual LLM switching: use `@` syntax to switch LLMs; Agent can switch via tool calls; temporarily switches to fallback LLM on 429/API network issues
- i18n: bilingual Chinese and English

## WIP

- CLAW mode: Continuous Living Autonomous Worker / OpenClaw-like mode - heartbeat messages, automatic memory file updates
- Telegram remote control
- Webshell control
- Restore conversation: untested

## Planned

- WebUI
- Skills: just a bunch of markdown + summaries

## On Hold

- MCP (over http): do we really need to reinvent REST?
- Subagent and ACP: not important; ACP can easily become MCP/API

## Installation and Setup

### (Linux+MacOS+Android+(Untested)Windows) Install from source using uv

```shell
git clone https://github.com/Marven11/LinHai.git
cd LinHai
uv tool install --from . linhai

linhai init
linhai
```

### (WIP) Install from pypi

```shell
uv tool install linhai
# Using pipx: pipx install linhai
# Using system pip: pip install linhai
# Install with venv: python -m venv /tmp/linhai-venv && . /tmp/linhai-venv/bin/activate && pip install linhai
```

## Config

```shell
linhai -m 'Starting at [config.py](https://github.com/Marven11/LinHai/blob/main/linhai/config.py), summerize configuration supported by LinHai. If I want to modify config later, modify ~/.config/linhai/ for me'
```

## Disclaimer

By downloading this product through Github, PYPI, or other channels, you agree to the following terms.

```markdown
This product consists solely of source code (hereinafter referred to as "the Product"). All code files, configuration documents, and development configurations are part of "the Product". This project is developed within the People's Republic of China and is governed by PRC law. However, the Product does not guarantee legality in all jurisdictions; users should assess and comply with local laws.

Any user who provides services or products based on the Product must provide the final user with the Product, including this disclaimer, and provide clear risk warnings. Losses caused by the final user's lack of awareness are not the responsibility of the project developers.

This project requires third-party AI model services. The Product ensures reasonable service invocation through rate limiting, usage estimation, highlight warnings, and other mechanisms. The Product guarantees reasonable invocation of services and displays fee-related data in real-time and accurately. Provided that the developers have no intentional or gross negligence, the project developers are not liable if users misconfigure, ignore fee indicators and estimated costs, or overlook third-party service billing rules.

Users must avoid configuring functions explicitly documented as dangerous, such as "bypass virtualization" or "allow arbitrary command execution." The Product only guarantees no losses when properly configured. Losses caused by user misconfiguration, enabling dangerous features, or bypassing security mechanisms are not the responsibility of the project developers.

This product is designed for three scenarios: personal project programming, security CTF testing, and simple document writing. It was not designed for commercial project programming, real-world penetration testing, or other scenarios outside its design scope. The Product is only responsible for losses within the designed scenarios.

The testing tools and payloads integrated into the Product have been deliberately weakened and can only be used for "personal project vulnerability testing" and "CTF challenge testing." They cannot bypass commercial firewalls, antivirus software, or security monitoring systems. Provided that the developers have no intentional or gross negligence, if users strengthen or add testing tools and payloads and use them outside the designed purposes, the project developers are not responsible.
```
