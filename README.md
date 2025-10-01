# 林海漫游

自用编程Agent，设计框架参考Claude Code

当前Agent能力依然很差，暂不上传pypi

![social-preview](./assets/social-preview.jpg)

## 特点

- 使用Markdown+JSON作为工具调用格式，可一次性调用多个工具
- 支持OpenAI接口
- 支持修改代码、运行命令、爬取网上文章（selenium+firefox）
- 历史消息过长时自动压缩

## 使用

创建[config.toml](./config-example.toml)，然后用一行命令启动：

```shell
python -m linhai agent --config ./config.toml
```

## TODO

自动完成CTF题目

# 参考

https://github.com/shareAI-lab/analysis_claude_code

https://mp.weixin.qq.com/s/o4pu8QX1tRIPBRlFJqrX3A

