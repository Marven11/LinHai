# Agents

This document describes the agents used in the LinHai system.

## Overview

LinHai is an AI agent system with modular tools and plugins. Agents are configured via TOML files and support various LLM providers.

## Configuration

Agents are defined in `config.toml` under the `[agents]` section. Each agent can have specific tools, memory settings, and LLM configurations.

## Usage

Run an agent using:
```bash
uv run python -m linhai --config ./config.toml -m 'your message'
```

## Available Agents

- Default agent with core tools
- Specialized agents for specific tasks (e.g., coding, testing)

Refer to `PROJECT.md` for development guidelines and `TODO.md` for current tasks.