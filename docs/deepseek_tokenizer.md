# DeepSeek Tokenizer 文档

DeepSeek 模型使用与 OpenAI 兼容的分词器。

## 分词器

DeepSeek 模型使用 `cl100k_base` 分词器，与 GPT-4 相同。

## Token 计数

可以使用 tiktoken 计算 DeepSeek 模型的 token 数量：

```python
import tiktoken

tokenizer = tiktoken.get_encoding("cl100k_base")
tokens = tokenizer.encode("你的文本")
token_count = len(tokens)
```

## 上下文长度

- DeepSeek-V2: 128K tokens
- DeepSeek-V2-Lite: 128K tokens
- DeepSeek-Coder-V2: 128K tokens

## 注意事项

- 中文文本通常会产生比英文字符更多的 token
- 特殊字符和空格也会计入 token
- 模型输入和输出都计入 token 限制

## 参考

- [DeepSeek 官方文档](https://platform.deepseek.com/api-docs/)
- [tiktoken GitHub](https://github.com/openai/tiktoken)