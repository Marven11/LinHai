# 解析Agent回答流程重构设计

## 1. 当前设计分析

### 1.1 当前架构
- **LLM层**: 生成`Answer`对象，包含`AnswerToken`流
- **Agent层**: `generate_response`遍历`Answer`，发送`AnswerToken`到`agent_answer`队列
- **CLI层**: 接收`AnswerToken`，使用`TokenParser`解析为三类token，通过`MessageWidget`展示

### 1.2 主要问题
1. **解析逻辑分散**: Token解析在CLI侧完成，但token生成在Agent侧
2. **消息传递复杂**: 需要传递原始token和解析后token两种格式
3. **打断处理不一致**: 打断逻辑分布在Agent和CLI中
4. **扩展性差**: 新增消息类型需要修改多个层级

## 2. 新设计目标

### 2.1 核心目标
1. **集中解析**: 在Agent侧完成token到segment的解析
2. **统一接口**: 使用segment作为CLI和Agent之间的唯一消息格式
3. **清晰状态**: 明确解析状态和打断机制
4. **易于测试**: 独立的解析逻辑便于单元测试

### 2.2 设计原则
- **单一职责**: ParsedAnswer只负责解析，不负责UI展示
- **异步友好**: 使用async/await和asyncio.Queue处理流式数据
- **向后兼容**: 逐步替换，确保现有功能不受影响

## 3. 详细设计

### 3.1 核心数据结构

#### 3.1.1 Segment定义
```python
from typing import Literal, TypedDict

class Segment(TypedDict):
    segment_type: Literal["reasoning", "normal", "toolcall"]
    content: str
    is_finished: bool
```

#### 3.1.2 ParsedAnswer类
ParsedAnswer不可迭代，提供segment_queue供CLI直接访问segment。
```python
class ParsedAnswer:
    def __init__(self, answer: Answer, lifecycle: Lifecycle):
        ...
        
    async def start_parsing(self):
        """启动解析任务"""
        self.parsing_task = asyncio.create_task(self._parse_answer())
        
    async def _parse_answer(self):
        """解析AnswerToken流，生成segment"""
        try:
            # 解析逻辑实现
            async for token in self.answer:
                # 检查是否被中断
                if self.interrupted:
                    # 设置中断标志，正常退出循环
                    break
                
                # 根据当前状态处理token
                # ...
                
        finally:
            self.is_finished = True
        
    async def wait_parsing(self) -> bool:
        """等待解析完成，返回是否正常结束（未被中断）"""
        if self.parsing_task:
            await self.parsing_task
        # 返回True表示正常结束，False表示被中断
        return not self.interrupted
```

CLI可以通过`parsed_answer.segment_queue`获取segment，而不是通过迭代。

### 3.2 解析状态机

禁止手动实现解析流程，必须使用已有的TokenParser解析

### 3.3 Agent层修改

#### 3.3.1 generate_response函数
```python
async def generate_response(...) -> None:
    # 生成Answer
    answer = await model.answer_stream(messages)
    
    # 创建ParsedAnswer
    parsed_answer = ParsedAnswer(answer, self.lifecycle)
    await parsed_answer.start_parsing()
    
    # 发送到新队列
    await self.group_chat.send("parsed_agent_answer", parsed_answer)
    
    # 等待解析完成，检查是否被中断
    completed_normally = await parsed_answer.wait_parsing()
    if not completed_normally:
        # 被中断，直接返回，不执行后续工具调用等
        return
    
    # 后续处理（工具调用等）
    # ...
```

#### 3.3.2 队列管理
- **删除**: `agent_answer`队列
- **新增**: `parsed_agent_answer`队列，传输ParsedAnswer对象

### 3.4 CLI层修改

#### 3.4.1 消息处理流程
```python
async def watch_parsed_agent_answer_queue(self):
    while True:
        parsed_answer = await self.group_chat.receive("parsed_agent_answer")
        
        # 持续从segment_queue获取segment，直到解析完成
        while not parsed_answer.is_finished:
            try:
                # 使用asyncio.wait_for避免永久阻塞
                segment = await asyncio.wait_for(
                    parsed_answer.segment_queue.get(), 
                    timeout=0.1
                )
                # 创建对应widget
                widget = self.create_widget_for_segment(segment)
                self.mount_widget(widget)
            except asyncio.TimeoutError:
                # 检查解析是否完成
                continue
```

注意：Python的asyncio.Queue没有像Go channel那样的关闭机制，因此需要其他方式判断解析完成。可以：
1. 在ParsedAnswer中添加`is_finished`属性，解析完成后设为True
2. 使用特殊的结束segment（如`{'type': 'end_of_stream'}`）
3. 上述代码示例采用检查`is_finished`属性的方式

#### 3.4.2 MessageWidget适配
- 移除TokenParser依赖
- 直接接收segment并展示
- 支持动态添加segment内容

### 3.5 打断处理

#### 3.5.1 新的中断流程
在重构后，不再有Agent.interrupt方法。中断处理完全由Answer.interrupt负责，通过以下方式触发：

1. **用户打断**：在generate_response的token循环中检测到用户输入时，直接调用`answer.interrupt(cli_message, runtime_message)`并分别指定两个消息
2. **插件打断**：通过lifecycle回调触发中断，回调中可以调用`answer.interrupt(cli_message, runtime_message)`并分别指定两个消息
3. **工具调用失败**：通过lifecycle回调传递Answer对象，让相关处理器处理

#### 3.5.2 用户输入检查
- 在generate_response的token循环中检查用户输入
- 有输入时直接调用`answer.interrupt(cli_message, runtime_message)`
- 不再通过Agent.interrupt方法中转

### 3.6 生命周期集成

#### 3.6.1 回调时机
1. **before_parsing**: 解析开始前
2. **after_segment**: 每个segment生成后
3. **after_parsing**: 解析完成后

#### 3.6.2 插件支持
- 插件可以监听segment生成事件
- 可以修改segment内容或添加新segment

## 4. 实现步骤

### 阶段1: 基础框架
1. 创建`linhai/parsed_message.py`
2. 实现Segment和ParsedAnswer基础类，使其提供segment_queue供CLI访问
3. 编写单元测试（不含具体unittest代码，见第6节）

### 阶段2: Agent集成
1. 修改`generate_response`使用ParsedAnswer
2. 添加`parsed_agent_answer`队列
3. 移除`agent_answer`队列发送
4. **删除打断逻辑**：删除`Agent.interrupt`方法，所有中断逻辑迁移到`Answer.interrupt`

### 阶段3: CLI集成
1. 修改`watch_agent_answer_queue`为`watch_parsed_agent_answer_queue`
2. 适配MessageWidget使用segment
3. 移除TokenParser

### 阶段4: 测试验证
1. 运行所有unittest
2. 手动测试各种场景
3. 确保向后兼容

## 5. 打断处理优化

### 5.1 当前状况分析
当前代码中，`self.current_answer`属性在以下地方被使用：
1. **Agent.interrupt方法**（第139-161行）：用于中断当前回答并发送相关消息
2. **Subagent违规检查**（violation_checker.py）：用于获取当前回答的完整内容以进行规则检查
3. **generate_response方法**：用于跟踪当前正在生成的回答

### 5.2 重构目标
1. **删除Agent.interrupt方法**：将中断逻辑完全迁移到Answer.interrupt
2. **保留self.current_answer属性**：由于subagent依赖此属性，暂时保留以供其使用
3. **简化中断流程**：让Answer负责完整的打断逻辑，包括停止token生成和发送CLI消息

### 5.3 Answer协议修改
需要修改Answer协议，为interrupt方法添加发送cli消息的能力：
- 在Answer的构造器中传入必要的上下文（如group_chat、消息处理器等）
- `interrupt`方法接受两个参数：`cli_message: str`和`runtime_message: str`
  - `cli_message`: 发送到CliRuntimeNotice的消息，必须提供
  - `runtime_message`: 发送到RuntimeMessage的消息，必须提供（不允许为None）
- 在`interrupt`内部停止token生成，并发送相应的cli消息和runtime消息

### 5.4 新中断流程
```python
# Answer.interrupt实现
async def interrupt(self, cli_message: str, runtime_message: str):
    """
    停止token生成并发送中断消息。
    
    参数:
        cli_message: 发送到CliRuntimeNotice的消息，必须提供
        runtime_message: 发送到RuntimeMessage的消息，必须提供（不允许为None）
    """
    # 停止token生成
    self._stop_token_generation()
    
    # 发送cli消息到group_chat
    await self.group_chat.send("cli_runtime_notice", 
                               CliRuntimeNotice(level="WARNING", content=cli_message))
    
    # 发送RuntimeMessage到消息处理器
    self.message_handler.add(RuntimeMessage(runtime_message))

# 删除Agent.interrupt方法，但保留self.current_answer属性供subagent使用
# 在generate_response中，仍然维护self.current_answer = answer
# 但不再通过Agent.interrupt进行中断
```

### 5.5 用户打断处理
在`generate_response`的token循环中，当检测到用户输入时，直接调用`answer.interrupt()`并分别指定消息：
```python
if not self.group_chat.is_empty("user_message"):
    # 获取用户消息
    msg = await self.receive_one_user_message()
    # 直接中断当前回答，必须分别指定CliRuntimeNotice和RuntimeMessage的消息
    await answer.interrupt(
        cli_message="Agent被用户打断",          # 给用户看的提示
        runtime_message="用户打断了你的回答，请处理新输入"  # 给agent看的内部消息
    )
    # 处理用户消息
    await self.handle_user_message(msg)
    return
```

注意：调用者必须分别提供两个消息，Answer.interrupt方法要求两个参数都必须提供且不为None。

### 5.6 Subagent依赖处理
由于subagent的violation_checker插件依赖于`agent.current_answer`来获取完整回答内容，在重构初期保持此属性可用。长期来看，可以考虑：
1. 修改lifecycle回调，将Answer对象作为参数传递给subagent相关方法
2. 或让subagent通过其他方式获取完整回答内容（如从ParsedAnswer或消息队列）

### 5.7 ParsedAnswer中的中断处理
- 当`answer.interrupt()`被调用后，`ParsedAnswer`应设置`interrupted = True`
- 在解析循环中检查`interrupted`标志，如果为True则正常退出循环
- `wait_parsing()`方法返回`False`表示被中断
- `generate_response`检查`wait_parsing()`的返回值，如果为`False`则直接返回，不执行后续流程（工具调用等）

## 6. 单元测试策略

### 6.1 测试目标
确保ParsedAnswer能够正确解析各种类型的AnswerToken流，并正确处理边界情况和错误场景。

### 6.2 测试场景

#### 6.2.1 基础解析测试
- **普通文本解析**：验证纯文本能够正确解析为单个normal segment
- **包含换行的文本**：验证换行符能够正确保留在segment内容中
- **空文本解析**：验证空answer不会产生任何segment

#### 6.2.2 工具调用解析测试
- **单个工具调用**：验证包含一个工具调用的文本能够正确解析为normal、toolcall、normal三个segment
- **多个工具调用**：验证连续多个工具调用能够正确解析为多个toolcall segment
- **不完整的工具调用**：验证缺少结束标记的工具调用能够正确解析为toolcall segment（即使不完整）
- **特殊字符的工具调用**：验证包含转义字符的JSON内容能够正确解析

#### 6.2.3 推理内容解析测试
- **纯推理内容**：验证只有推理内容的answer能够正确解析为reasoning segment
- **推理后接普通内容**：验证先推理后普通的answer能够正确解析为两个segment
- **交替推理和普通内容**：验证reasoning和normal交替出现的answer能够正确解析为多个交替的segment

#### 6.2.4 打断和错误处理测试
- **中断的answer解析**：验证被中断的answer能够正确返回已解析的部分，并正常结束
- **解析过程中的异常**：验证解析过程中遇到异常能够正确处理，不影响整体流程

#### 6.2.5 边界情况测试
- **大内容解析**：验证大文本（如10KB）能够正确解析为一个segment
- **并发解析**：验证多个ParsedAnswer实例能够并发解析而不互相干扰
- **特殊字符和编码**：验证各种特殊字符（如Unicode、转义字符）能够正确解析

### 6.3 测试工具
- 使用unittest框架，配合asyncio测试异步代码
- 创建MockAnswer类，模拟各种AnswerToken流
  - 支持普通文本流
  - 支持包含reasoning和normal交替的流
  - 支持中断模拟
- 创建MockLifecycle类，验证回调调用情况

### 6.4 断言重点
- segment类型是否正确
- segment内容是否完整
- segment顺序是否正确
- 解析完成后是否正常结束
- 中断情况下是否能够正常处理

---
*设计审核通过后开始实现*