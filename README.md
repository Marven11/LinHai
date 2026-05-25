# LinHai

A Multi-Machine Control Coding/Hacking Agent running on Mac/Linux/Android.

[中文文档](./README_zh-CN.md)

![social-preview](./assets/social-preview.jpg)

<p align="center">
  <a href="https://pypi.org/project/linhai/"><img src="https://img.shields.io/pypi/v/linhai?style=flat&amp;colorA=222222&amp;colorB=3776AB" alt="PyPI version"></a>
  <a href="https://pypi.org/project/linhai/"><img src="https://img.shields.io/pypi/pyversions/linhai?style=flat&amp;colorA=222222&amp;colorB=3776AB" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0-58A6FF?style=flat&amp;colorA=222222" alt="License"></a>
</p>

## Demo

![[demo](https://asciinema.org/a/N6zgQTzjXTNKohXF)](./assets/demo.gif)

## Any bash process is a first-class machine.

SSH. Sudo. Docker exec. ADB shell. Connect any of them --- LinHai treats it like local. Multi-hop is just stacking connections: ssh to the target, sudo bash inside it, and both are first-class machines in the same session.

- Dynamically connect any bash process (ssh/sudo bash/docker exec/adb shell) as a machine
- Multi-hop connections: chain ssh into sudo bash with the same toolset
- Long-running processes automatically background
- argv enforced to avoid blind `&&` chaining
- Background processes controllable via stdio --- REPLs just work

## See every token. Interrupt whenever you want.

Thinking. Conversation. Tool calls. Everything streams as it happens. When the agent goes off track, interrupt mid-generation --- no waiting for a full response you're going to throw away.

- All tokens stream in real time: thinking, conversation, and tool calls
- Dynamically interrupt agent output
- Context stats, token costs, and process management in dedicated panels
- Real-time display of context length and token consumption
- Nerd fonts supported

## Sandbox-first. No approval spam.

YOLO-mode sandboxing --- the agent works within rules, not around them. No per-action approval dialogs slowing you down. File read/write, terminal control, process control: one toolset for development and ops.

- Sandbox-based authorization instead of per-approval
- File read/write permission rules and process sandbox enforced
- MCP servers connect on demand and disconnect when idle --- **zero** token overhead when not in use
- Even dynamically connected MCP runs inside the sandbox

## Context that compacts itself.

Fully automatic, cache-aware context compression. The agent decides what to keep and what to compact, maintaining cache hit rate above **90%** --- you never hit the context ceiling.

- Fully automatic cache-aware context compression
- Agent automatically cleans context while maintaining 90%+ cache hit rate
- Three-layer message organization: pinned, regular, notification (inspired by Codex)

## Planning mode. LLM switching. i18n.

Planning mode: the agent manages its own status, todo, and design documents, and doesn't stop until every item is checked off. Inspired by amp and oh-my-opencode.

- Planning mode: autonomous status, todo, and design document management
- Auto/manual LLM switching via `@` syntax or tool calls
- Automatic fallback to alternative LLM on 429/API network issues
- Bilingual Chinese and English interface

## WIP

CLAW mode --- Continuous Living Autonomous Worker. Heartbeat messages, automatic memory file updates, the agent stays alive between sessions. Telegram remote control. Webshell control. Restore conversation: untested.

## Planned

WebUI. Skills: markdown playbooks the agent can pick up on the fly.

## On Hold

MCP over HTTP --- do we really need to reinvent REST? Subagent and ACP --- not important; ACP can become MCP/API.

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
