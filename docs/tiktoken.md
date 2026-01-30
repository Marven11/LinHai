# tiktoken 文档

tiktoken 是 OpenAI 开源的快速分词器，用于将文本转换为 token 序列。

## 安装

```bash
pip install tiktoken
```

## 使用

```python
import tiktoken

# 获取编码
tokenizer = tiktoken.get_encoding("cl100k_base")

# 编码文本
tokens = tokenizer.encode("Hello, world!")
print(tokens)  # [9906, 11, 1917, 0]

# 解码
text = tokenizer.decode(tokens)
print(text)  # "Hello, world!"
```

## 编码类型

- `cl100k_base`: 用于 GPT-4, GPT-3.5-turbo, text-embedding-ada-002 等
- `p50k_base`: 用于 Codex 模型
- `r50k_base`: 用于 GPT-3 模型

## 参考

- [GitHub 仓库](https://github.com/openai/tiktoken)
- [OpenAI Cookbook](https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb)