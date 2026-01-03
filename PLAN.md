# Secret系统实现规划

## 1. 总体目标

实现一个完整的secret系统，使Agent能够安全地处理敏感信息（如API密钥、密码等），通过`<$KEY$>`格式引用secret，并在工具调用中通过`with_secret`字段指定使用的secret键。

## 2. 系统架构

### 2.1 核心组件

1. **SecretManager** - 管理secret的加载、存储和替换
2. **SecretInterceptorPlugin** - 拦截工具调用和结果的插件
3. **配置系统** - 支持在`[tools.secret]`中配置secret文件路径
4. **消息格式扩展** - ToolCallMessage添加`with_secret`字段

### 2.2 数据流

```
Agent初始化 → 加载配置 → 创建SecretManager → 注册插件
↓
工具调用 → before_tool_call(替换<$KEY$>为实际值) → 执行工具
↓
工具返回 → after_tool_call(根据with_secret处理结果) → 返回给LLM
```

## 3. 详细实施步骤

### 3.1 完善SecretManager (linhai/secret.py)

**需要添加的方法：**

1. `replace_secrets_in_object(obj: Any, secret_keys: list[str]) -> Any`
   - 递归处理字典、列表、字符串
   - 将字符串中的`<$KEY$>`替换为对应的secret值
   
2. `mask_secrets_in_object(obj: Any) -> Any`
   - 递归处理对象
   - 将secret值替换回`<$KEY$>`格式

3. `get_available_secrets_message() -> str`
   - 返回当前可用secret键和描述的格式化字符串
   - 例如："当前可用secret键: <$OPENAI_API_TOKEN$> - 调用OpenAI的API token; <$SSH_PASSWORD$> - SSH私钥的解锁密码"

### 3.2 创建SecretInterceptorPlugin (放在linhai/secret.py中)

**类结构：**
```python
class SecretInterceptorPlugin:
    def __init__(self, group_chat: GroupChat):
        self.group_chat = group_chat
    
    async def before_tool_call(self, tool_call: ToolCallMessage) -> bool:
        # 替换参数中的secret键
        pass
    
    async def after_tool_call(self, agent, tool_call, tool_result, success) -> Any:
        # 处理工具结果
        pass
    
    def register(self, lifecycle):
        lifecycle.register_before_tool_call(self.before_tool_call)
        lifecycle.register_after_tool_call(self.after_tool_call)
```

**before_tool_call逻辑：**
1. 检查tool_call.with_secret字段
2. 如果有secret_keys，调用secret_manager.replace_secrets_in_object()替换tool_call.function_arguments
3. 返回False（不阻止工具调用）

**after_tool_call逻辑：**
- **情况A**：工具调用指定了with_secret
  1. 将tool_result中的secret值替换回`<$KEY$>`格式
  2. 构建格式化消息：`<<masked>><<message>>工具内容包含<$KEY$>secret的内容，已替换<<message>><<replaced>><<result>>{替换后的结果}<<result>><<replaced>><<masked>>`
  3. 返回RuntimeMessage

- **情况B**：工具调用未指定with_secret，但结果包含secret值
  1. 返回RuntimeMessage："工具调用的结果包含<$KEY$>格式secret键的内容，已拦截。如果需要查看内容则需要使用with_secret指定对应的键，其中的secret值会被secret键拦截"

- **情况C**：其他情况，返回None（不替换结果）

### 3.3 修改Agent初始化

**位置**：linhai/agent相关初始化代码

**逻辑：**
1. 读取配置，检查是否有`tools.secret`配置项
2. 如果有，创建SecretManager实例，设置config_path，调用load()方法
3. 将SecretManager注册到group_chat
4. 创建SecretInterceptorPlugin实例，注册到lifecycle
5. 在prompt中添加可用的secret键信息（通过appending message）

### 3.4 配置系统集成

- **配置文件示例**（config.toml）：
  ```toml
  [tools.secret]
  config_path = "./.secret.toml"
  ```

- **Secret文件格式**（.secret.toml）：
  ```toml
  [secrets]
  OPENAI_API_TOKEN = { value = "sk-xxx", description = "OpenAI API token" }
  SSH_PASSWORD = { value = "mypassword", description = "SSH私钥密码" }
  ```

## 4. 测试计划

### 4.1 单元测试
1. **SecretManager测试**：
   - 加载secret文件
   - 替换字符串中的secret键
   - 检查是否包含secret值
   - 获取可用secret消息

2. **SecretInterceptorPlugin测试**：
   - before_tool_call的secret替换
   - after_tool_call的结果拦截
   - after_tool_call的结果masking

### 4.2 集成测试
按照TODO.md中的要求：

1. **测试1**：读取secret文件并报告
   ```bash
   uv run python -m linhai --config config.toml -m '尝试读取./.secret.toml并报告其中的api_key，输出到/tmp/read_secret_toml_result.txt然后退出，如果读取不了则报告发生了什么错误'
   ```

2. **测试2**：使用secret编写脚本
   ```bash
   uv run python -m linhai --config config.toml -m '使用给定的deepseek api key编写一个脚本，调用deepseek api并打印结果，测试结果输出到/tmp/use_secret_result.txt'
   ```

## 5. 注意事项

1. **Secret键格式**：严格使用`<$KEY$>`格式，注意转义处理
2. **插件注册**：插件不在内部检查是否启用，由初始化代码控制
3. **递归处理**：工具参数可能是嵌套结构（字典、列表），需要递归处理
4. **错误处理**：secret文件不存在或格式错误时，应有清晰的错误提示
5. **性能考虑**：secret替换可能频繁调用，注意效率
6. **安全考虑**：确保secret值不会泄露到LLM上下文