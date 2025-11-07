# 林海漫游

自用编程Agent，设计框架参考Claude Code

当前Agent能力依然很差，暂不上传pypi

![social-preview](./assets/social-preview.jpg)

## 特点

- 使用Markdown+JSON作为工具调用格式，可一次性调用多个工具
- 支持OpenAI接口
- 支持修改代码、运行命令、爬取网上文章（selenium+firefox）
- 历史消息过长时自动压缩
- 目录更改检测（默认关闭，需在配置中启用）

## 使用

创建[config.toml](./config-example.toml)，然后用一行命令启动：

```shell
python -m linhai --config ./config.toml
```

### 目录更改检测功能

目录更改检测功能可以自动检测当前工作目录的变化，并在检测到特定文件（LINHAI.md, AGENTS.md, CLAUDE.md）时自动将其内容添加到对话中。

默认情况下此功能是关闭的。要启用它，请在配置文件中添加：

```toml
[agent]
enable_directory_change_detection = true
```

启用后，当您切换到包含这些文件的目录时，Agent会自动读取文件内容并添加到对话上下文中。

## 警告

agent会自动加载当前目录的LINHAI.md, AGENTS.md和CLAUDE.md！

请不要在危险的文件夹中使用！

## TODO

自动完成CTF题目

# 参考

https://github.com/shareAI-lab/analysis_claude_code

https://mp.weixin.qq.com/s/o4pu8QX1tRIPBRlFJqrX3A

