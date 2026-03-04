# 阿里云百炼上下文缓存（Context Cache）

调用大模型时，不同推理请求可能出现输入内容的重叠（例如多轮对话或对同一本书的多次提问）。上下文缓存（Context Cache）技术可以缓存这些请求的公共前缀，减少推理时的重复计算。这能提升响应速度，并在不影响回复效果的前提下降低您的使用成本。

## 工作模式对比

为满足不同场景的需求，上下文缓存提供三种工作模式：

| 项目                      | 显式缓存               | 隐式缓存                                   | Session 缓存           |
| ------------------------- | ---------------------- | ------------------------------------------ | ---------------------- |
| 是否影响回复效果          | 不影响                 | 不影响                                     | 不影响                 |
| 用于创建缓存 Token 计费   | 输入 Token 单价的 125% | 输入 Token 单价的 100%                     | 输入 Token 单价的 125% |
| 命中缓存的输入 Token 计费 | 输入 Token 单价的 10%  | 输入 Token 单价的 20%                      | 输入 Token 单价的 10%  |
| 缓存最少 Token 数         | 1024                   | 256                                        | 1024                   |
| 缓存有效期                | 5 分钟（命中后重置）   | 不确定，系统会定期清理长期未使用的缓存数据 | 5 分钟（命中后重置）   |

说明：

- 使用 Chat Completions/DashScope API 时，显式缓存、隐式缓存两者互斥，单个请求只能应用其中一种模式
- 使用 Responses API 时，未启用 Session 缓存时，若模型支持将启用隐式缓存

## 显式缓存

与隐式缓存相比，显式缓存需要显式创建并承担相应开销，但能实现更高的缓存命中率和更低的访问延迟。

### 使用方式

在 messages 中加入 `"cache_control": {"type": "ephemeral"}` 标记，系统将以每个 `cache_control` 标记位置为终点，向前回溯最多 20 个 `content` 块，尝试命中缓存。

单次请求最多支持加入 4 个缓存标记。

**未命中缓存**：系统将从 messages 数组开头到 `cache_control` 标记之间的内容创建为新的缓存块，有效期为 5 分钟。

- 缓存创建发生在模型响应之后，建议在创建请求完成后再尝试命中该缓存
- 缓存块的内容最少为 1024 Token

**命中缓存**：选取最长的匹配前缀作为命中的缓存块，并将该缓存块的有效期重置为 5 分钟。

### 支持的模型

**千问 Max**：qwen3-max

**千问 Plus**：qwen3.5-plus、qwen-plus

**千问 Flash**：qwen3.5-flash、qwen-flash

**千问 Coder**：qwen3-coder-plus、qwen3-coder-flash

**千问 VL**：qwen3-vl-plus（仅中国内地版）

**DeepSeek-阿里云**：deepseek-v3.2（仅中国内地版）

说明：以上所列模型在中国内地版和国际版均支持显式缓存功能（特别说明的除外），暂不支持快照与 latest 模型。

### 快速开始示例

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 模拟的代码仓库内容，最小可缓存提示词长度为 1024 Token
long_text_content = "<Your Code Here>" * 400

# 发起请求的函数
def get_completion(user_input):
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": long_text_content,
                    # 在此处放置 cache_control 标记
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        # 每次的提问内容不同
        {"role": "user", "content": user_input},
    ]
    completion = client.chat.completions.create(
        model="qwen3-coder-plus",
        messages=messages,
    )
    return completion

# 第一次请求
first_completion = get_completion("这段代码的内容是什么")
print(f"第一次请求创建缓存 Token：{first_completion.usage.prompt_tokens_details.cache_creation_input_tokens}")
print(f"第一次请求命中缓存 Token：{first_completion.usage.prompt_tokens_details.cached_tokens}")

# 第二次请求，代码内容一致，只修改了提问问题
second_completion = get_completion("这段代码可以怎么优化")
print(f"第二次请求创建缓存 Token：{second_completion.usage.prompt_tokens_details.cache_creation_input_tokens}")
print(f"第二次请求命中缓存 Token：{second_completion.usage.prompt_tokens_details.cached_tokens}")
```

输出示例：

```
第一次请求创建缓存 Token：1605
第一次请求命中缓存 Token：0
====================
第二次请求创建缓存 Token：0
第二次请求命中缓存 Token：1605
```

### 计费规则

显式缓存仅影响输入 Token 的计费方式：

- **创建缓存**：新创建的缓存内容按标准输入单价的 125% 计费。若新请求的缓存内容包含已有缓存作为前缀，则仅对新增部分计费（即新缓存 Token 数减去已有缓存 Token 数）
- **命中缓存**：按标准输入单价的 10% 计费
- **其他 Token**：未命中且未创建缓存的 Token 按原价计费

创建缓存所用的 Token 数通过 `cache_creation_input_tokens` 参数查看，命中缓存的 Token 数通过 `cached_tokens` 参数查看。

### 可缓存内容

仅 `messages` 数组中的以下消息类型支持添加缓存标记：

- 系统消息（System Message）
- 用户消息（User Message）
- 助手消息（Assistant Message）
- 工具消息（Tool Message，即工具执行后的结果）

若请求包含 `tools` 参数，在 `messages` 中添加缓存标记还会缓存其中的工具描述信息。

### 缓存限制

- 最小可缓存提示词长度为 1024 Token
- 缓存采用从后向前的前缀匹配策略，系统会自动检查最近的 20 个 content 块。若待匹配内容与带有 `cache_control` 标记的消息之间间隔超过 20 个 content 块，则无法命中缓存
- 仅支持将 `type` 设置为 `ephemeral`，有效期为 5 分钟
- 单次请求最多可添加 4 个缓存标记

## 隐式缓存

隐式缓存为自动模式，无需额外配置，且无法关闭，适合追求便捷的通用场景。系统会自动识别请求内容的公共前缀并进行缓存，但缓存命中率不确定。对命中缓存的部分，按输入 Token 标准单价的 20% 计费。

### 支持的模型

**中国内地**：

- **千问 Max**：qwen3-max、qwen-max
- **千问 Plus**：qwen-plus
- **千问 Flash**：qwen-flash
- **千问 Turbo**：qwen-turbo
- **千问 Coder**：qwen3-coder-plus、qwen3-coder-flash
- **DeepSeek**：deepseek-v3.2、deepseek-v3.1、deepseek-v3、deepseek-r1
- **Kimi**：kimi-k2.5、kimi-k2-thinking、Moonshot-Kimi-K2-Instruct
- **GLM**：glm-5、glm-4.7、glm-4.6
- **MiniMax**：MiniMax-M2.5、MiniMax-M2.1
- **千问 VL**：qwen3-vl-plus、qwen3-vl-flash、qwen-vl-max、qwen-vl-plus
- **角色扮演**：qwen-plus-character
- **数据挖掘**：qwen-doc-turbo

暂不支持快照与 latest 模型。

### 工作方式

向支持隐式缓存的模型发送请求时，该功能会自动开启：

1. **查找**：收到请求后，系统基于前缀匹配原则，检查缓存中是否存在请求中 `messages` 数组内容的公共前缀
2. **判断**：若命中缓存，系统直接使用缓存结果进行后续部分的推理；若未命中，系统按常规处理请求，并将本次提示词的前缀存入缓存

系统会定期清理长期未使用的缓存数据。上下文缓存命中概率并非 100%，即使请求上下文完全一致，仍可能未命中。

### 提升命中缓存的概率

隐式缓存的命中逻辑是判断不同请求的前缀是否存在重复内容。为提高命中概率，请将重复内容置于提示词开头，差异内容置于末尾。

- 文本模型：假设系统已缓存"ABCD"，则请求"ABE"可能命中"AB"部分，而请求"BCD"则无法命中
- 视觉理解模型：对同一图像或视频进行多次提问时，将图像或视频放在文本信息前会提高命中概率

### 计费规则

开启隐式缓存模式无需额外付费：

- 当请求命中缓存时，命中的输入 Token 按 `cached_token` 计费（单价为 `input_token` 单价的 20%）
- 未被命中的输入 Token 按标准 `input_token` 计费
- 输出 Token 仍按原价计费

示例：某请求包含 10,000 个输入 Token，其中 5,000 个命中缓存。费用计算如下：

- 未命中 Token (5,000)：按 100% 单价计费
- 命中 Token (5,000)：按 20% 单价计费
- 总输入费用相当于无缓存模式的 60%：(50% × 100%) + (50% × 20%) = 60%

可从返回结果的 `cached_tokens` 属性获取命中缓存的 Token 数。

## Session 缓存

Session 缓存是面向 Responses API 多轮对话场景的缓存模式。与显式缓存需要手动添加 `cache_control` 标记不同，Session 缓存由服务端自动处理缓存逻辑，只需通过 HTTP header 控制开关，按正常多轮对话方式调用即可。

### 使用方式

在请求 header 中添加以下字段即可控制 Session 缓存的开关：

- `x-dashscope-session-cache: enable`：开启 Session 缓存
- `x-dashscope-session-cache: disable`：关闭 Session 缓存，若模型支持将启用隐式缓存

使用 SDK 时，可通过 `default_headers`（Python）或 `defaultHeaders`（Node.js）参数传入该 header。

### 支持的模型

qwen3-max、qwen3.5-plus、qwen3.5-flash、qwen-plus、qwen-flash、qwen3-coder-plus、qwen3-coder-flash

Session 缓存仅适用于 Responses API，不适用于 Chat Completions API。

### 计费规则

Session 缓存的计费规则与显式缓存一致：

- 创建缓存：按输入 Token 标准单价的 125% 计费
- 命中缓存：按输入 Token 标准单价的 10% 计费
- 其他 Token：未命中且未创建缓存的 Token 按原价计费

命中缓存的 Token 数通过 `usage.input_tokens_details.cached_tokens` 参数查看。

### 约束限制

- 最小可缓存提示词长度为 1024 Token
- 缓存有效期为 5 分钟，命中后重置
- 仅适用于 Responses API，需配合 `previous_response_id` 参数进行多轮对话
- Session 缓存与显式缓存、隐式缓存互斥，开启后其他两种模式不生效

## 典型应用场景

如果您的不同请求有着相同的前缀信息，上下文缓存可以有效提升这些请求的推理速度，降低推理成本与首包延迟：

1. **基于长文本的问答**：适用于需要针对固定的长文本（如小说、教材、法律文件等）发送多次请求的业务场景
2. **代码自动补全**：在代码自动补全场景，大模型会结合上下文中存在的代码进行代码自动补全，上下文缓存可以缓存之前的代码，提升补全速度
3. **多轮对话**：实现多轮对话需要将每一轮的对话信息添加到 messages 数组中，因此每轮对话的请求都会存在与前轮对话前缀相同的情况，有较高概率命中缓存
4. **角色扮演或 Few Shot**：在角色扮演或 Few-shot 学习的场景中，您通常需要在提示词中加入大量信息来指引大模型的输出格式，这样不同的请求之间会有大量重复的前缀信息
5. **视频理解**：在视频理解场景中，如果对同一个视频提问多次，将 video 放在 text 前会提高命中缓存的概率

## 常见问题

**Q：如何关闭隐式缓存？**
A：无法关闭。隐式缓存对所有适用模型请求开启的前提是对回复效果没有影响，且在命中缓存时降低使用成本，提升响应速度。

**Q：为什么创建显式缓存后没有命中？**
A：有以下可能原因：

- 创建后 5 分钟内未被命中，超过有效期系统将清理该缓存块
- 最后一个 `content` 与已存在的缓存块的间隔大于 20 个 `content` 块时，不会命中缓存，建议创建新的缓存块

**Q：显式缓存命中后，是否会重置有效期？**
A：是的，每次命中都会将该缓存块的有效期重置为 5 分钟。

**Q：不同账号之间的显式缓存是否会共享？**
A：不会。无论是隐式缓存还是显式缓存，数据都在账号级别隔离，不会共享。

**Q：相同账号使用不同模型显式缓存是否会共享？**
A：不会。缓存数据存在模型间隔离，不会共享。

**Q：为什么 usage 的 input_tokens 不等于 cache_creation_input_tokens 和 cached_tokens 的总和？**
A：为了确保模型输出效果，后端服务会在用户提供的提示词之后追加少量 Token（通常在 10 以内），这些 Token 在 `cache_control` 标记之后，因此不会被计入缓存的创建或读取，但会计入总的 `input_tokens`。
