# Secret系统实现规划

## 1. 总体目标

实现一个完整的secret系统，使Agent能够安全地处理敏感信息（如API密钥、密码等），通过`<$KEY$>`格式引用secret，并在工具调用中通过`with_secret`字段指定使用的secret键。

## 2. 系统架构

### 2.1 核心组件

1. **Secret字典** - 存储所有secret键值对的Python字典
2. **Secret处理函数** - 少量helper函数用于secret替换和掩码
3. **SecretInterceptorPlugin** - 拦截工具调用和结果的插件
4. **配置系统扩展** - 在`[tools.secret]`中配置secret文件路径
5. **消息格式扩展** - ToolCallMessage添加`with_secret`字段

### 2.2 数据流

```
Agent初始化 → 加载配置 → 读取secret文件到字典 → 注册插件
↓
工具调用 → before_tool_call(替换<$KEY$>为实际值) → 执行工具
↓
工具返回 → after_tool_call(根据with_secret处理结果) → 返回给LLM
```

## 3. 详细实施步骤

### 3.1 核心Helper函数设计

定义四个核心helper函数：

1. **加载secret配置**：从TOML文件加载secret到字典结构
2. **替换secret键**：递归处理对象，将`<$KEY$>`格式的secret键替换为实际值
3. **掩码secret值**：递归处理对象，将secret值替换回`<$KEY$>`格式
4. **生成可用secret消息**：格式化当前可用secret键和描述

### 3.2 SecretInterceptorPlugin设计

**插件职责：**
- **before_tool_call**：检查`with_secret`字段，使用helper函数替换参数中的secret键
  - 如果`with_secret`列表中的任何secret键在字典中未找到，则拦截工具调用，返回错误消息
  - 如果arguments中含有未在`with_secret`列表中指定的secret键（即`<$UNEXISTS$>`格式），则忽略不做替换
- **after_tool_call**：根据是否指定`with_secret`处理工具结果
  - 指定时：使用helper函数掩码结果中的secret值，返回格式化消息
  - 未指定但结果包含secret值：拦截结果并提示需要指定`with_secret`
  - 其他情况：不处理

### 3.3 Agent初始化修改

1. 读取配置，检查`tools.secret.config_path`配置项
2. 如果配置存在，加载secret文件到字典（文件不存在或格式错误时直接崩溃）
3. 创建SecretInterceptorPlugin实例，传入secret字典
4. 注册插件到lifecycle
5. 在prompt中添加可用secret键信息

**插件注册检测**：仅在agent初始化时检测是否应该注册插件（基于配置是否存在），插件内部不检测自身是否应该运行。

### 3.4 配置系统集成

- 扩展ToolConfig类，添加`secret_config_path`字段
- 配置文件示例：`config.toml`中添加`[tools.secret] config_path = "./.secret.toml"`
- Secret文件格式：TOML格式，每个secret包含value和description字段

### 3.5 错误处理设计

遵循"让其崩溃"原则，不尝试捕获和恢复错误：

1. **文件不存在错误**：secret配置文件不存在时，直接抛出异常，Agent启动失败
2. **格式错误处理**：TOML解析失败时，直接抛出异常，Agent启动失败
3. **Secret键未找到**：
   - 如果`with_secret`字段中指定的secret键在字典中未找到，插件拦截工具调用，返回错误消息
   - 如果arguments中含有未定义的`<$KEY$>`格式secret键（不在`with_secret`列表中），则忽略不做替换
4. **递归处理错误**：递归处理嵌套对象时不捕获异常，任何错误直接向上抛出
5. **插件注册错误**：插件注册失败时直接抛出异常，Agent启动失败

## 4. 测试计划

### 4.1 单元测试
1. **Helper函数测试**：测试加载、替换、掩码、消息生成函数的正确性
2. **SecretInterceptorPlugin测试**：测试before_tool_call和after_tool_call的各种情况
   - 测试`with_secret`中键未找到时的拦截行为
   - 测试arguments中未定义键的忽略行为
   - 测试各种错误情况的崩溃行为
3. **错误处理测试**：测试各种错误情况的直接崩溃行为

### 4.2 集成测试
按照TODO.md要求执行两个测试场景：
1. 读取secret文件并报告其中的api_key
2. 使用secret编写脚本调用API

## 5. 注意事项

1. **Secret键格式**：严格使用`<$KEY$>`格式，确保正确解析
2. **安全第一**：确保secret值不会泄露到LLM上下文
3. **崩溃原则**：错误处理采用"让其崩溃"策略，不尝试捕获和恢复
4. **向后兼容**：不影响现有功能，无secret配置时正常运作
5. **明确行为**：secret键未找到的两种情况（with_secret中 vs arguments中）有不同处理逻辑

## 6. 实施顺序

1. 首先扩展配置类和添加helper函数
2. 实现SecretInterceptorPlugin核心逻辑，特别是secret键未找到的差异化处理
3. 修改Agent初始化流程，实现插件注册检测
4. 编写单元测试验证各组件，特别是错误崩溃行为
5. 执行集成测试验证完整流程
6. 验证边界情况和错误场景的崩溃行为