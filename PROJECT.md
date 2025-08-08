# 项目介绍

林海漫游，一个专精软件工程和渗透攻击的AI Agent

# 项目TODOLIST

- [ ] 完成工具类
- [ ] 完成LLM对接部分
    - [x] 基本适配OpenAI
    - [x] 编写测试
    - [ ] 支持打断Token生成
- [ ] 完成Agent逻辑
    - [x] 基本聊天
    - [x] 工具调用
        - [x] 弃用OpenAI的残废工具调用，使用markdown json code block的形式让Agent调用工具
        - [ ] 添加更多工具
    - [ ] 任务规划
    - [ ] 用户响应
    - [ ] 历史压缩

# 代码风格与规范

- 没有特殊情况，数据传递一般使用TypedDict
- 多个对象之间的交流一般使用Queue
- 每个模块都应该有对应的unit test测试其的功能
- 没有特殊情况，每个新建的变量都要加上类型注释（type hint）
- 所有函数和方法都需要编写文档注释，写好输入输出的类型注释
- 没有特殊情况，不要使用`# `注释代码片段在干什么
- 类型检查器是必需的：类型检查器的输出可以极大帮助LLM修复漏洞
- 不要在语句结尾和空行处留下多余的空格

# LLM规范

如果你是辅助用户编写代码的机器人，你需要注意以下几点：

- 如果你遇到了什么问题，请询问用户
- 如果你思考了未来的任务，且任务不能一步完成，你应该在输出时提及你对未来的计划
    - 如：“当前我们遇到了...问题，未来应先...，然后...”
- 你应该注意上方的“代码风格与规范”，根据提及的代码风格编写代码

# Agent设计

## 架构设计

Agent具有以下功能

- 工具调用：调用各类MCP形式的工具
    - 为了减少Prompt长度，工具的文档保存均保存在单独的文件中
    - Agent在调用工具时，首先需要根据工具对应的文档条目名查询文档，获得工具的用法，然后调用工具
    - 为了完成工作，Agent会不可避免地需要操控用户的电脑，有些操作需要获得用户确认
- 历史压缩：在上下文过长时压缩上下文
- 用户响应：分析用户的输入，并据此调整当前任务等信息
- 任务规划：在任务开始时规划TODOLIST，指定当前任务的最终目标和当前已经规划的任务
    - 对于渗透任务来说未来的小任务往往是未知的，在打进机器之前难以知道机器内部的信息
- 全局记忆：在单独的文件中保存用户的偏好等，Agent在运行时会动态修改这个全局记忆
    - 在开始时全局记忆只保存用户使用的语言（中文/英文/...）

## 历史总结

Agent会在任务开始时或其他适当的时机总结当前的任务进程和任务信息，包括：

1. 主要目标：主要任务是什么，任务需要完成什么目标，达到什么效果
2. 关键概念：文档或其他信息源中提到的关键技术概念
    - 为了节省资源，这里仅总结该任务专有的信息
    - 如python基础等公开已知的、LLM已经学会的信息不在此列
    - 这些技术概念应该关键到没有这些信息Agent就没法良好地完成工作
3. 文件代码：关键且有用的各类文件和代码片段
4. 问题与解：Agent在执行任务时遇到的各类问题，如果有解法则提供解法
5. 待办任务：当前Agent规划好的，需要完成的各类任务，使用分级bullet point记录，`[ ]`和`[x]`标记未完成和已经完成
6. 当前任务：当前Agent正在处理的任务
7. 未来任务：列出未来可能需要完成的任务
8. 用户输入：用户提出的每一个要求，提供的每一个信息，**用户的每一条信息都很重要！**

总结应该尽量简洁

## 响应生成

Agent在调用LLM生成Token时，Token的生成可能会被Agent打断，此时Agent应该停止手中的工作，回到等待用户新消息的状态

## 状态转移

### 状态：等待用户

这是Agent的初始状态：等待用户的消息以进行下一步

当收到用户消息时执行“消息响应”流程

此时不应该接收到工具执行结果，如果接收到了则忽略，最多打印一条log

### 状态：自动运行

这是Agent调用工具解决问题的状态，Agent此时应该全自动地调用工具完成任务

Agent在发送工具调用消息，等待工具处理完成返回消息时处于此状态

当收到工具执行结果时执行“消息响应”流程

当收到用户消息时，暂时先把用户的消息保存下来，在接收到工具执行结果之后转到“消息响应”流程一起回复

### 状态：暂停运行

因其他原因暂停运行

当收到用户消息或者工具执行结果时执行“消息响应”流程

## 消息响应

Agent的运行过程为响应式，Agent需要通过Queue接受用户的消息和工具的运行结果

在主循环中，Agent应该根据当前任务自动运行，同时适时await用户和工具发来的消息

当获得消息时，Agent应：

1. 分析消息，提取其中的关键信息
2. 如果需要的话，改写全局记忆和当前任务
3. 根据当前的信息回复用户或调用工具
4. 跳转到其他状态
    - 如果回复了用户则跳转到等待用户状态
    - 如果调用了其他工具则跳转到自动运行状态

## 工具调用

### 设计

Agent可以使用Markdown中的JSON code block调用工具，每个工具都是一个函数，函数的输入和输出都可以被JSON序列化

工具可能会抛出错误。如果抛出的错误属于ToolError类则需要将对应的错误展示给LLM看

因此，工具的输出Queue输出的是一个符合llm.py中Messgae Protocol的Message:
- ToolResultMessage: 表示工具输出的结果，用字符串保存结果，可以被转为role=tool的message
- ToolErrorMessage: 表示工具输出的错误，用字符串保存结果，可以被转为role=tool的message

~~工具调用需要附上调用的ID号，上方两个message也都包含对应的ID以便转为message~~

因为已经弃用OpenAI的Function Calling，所以工具调用不应该附上调用的ID号

除了计算器等常见的工具之外，还有一个特殊的工具`lookup_tool_docs`用于查询工具的使用文档。

`lookup_tool_docs`的输入是工具的名字，输出是对应工具的文档。这样我们就可以把工具的文档放在其他地方，降低prompt的长度

为了让OpenAI库不出错，禁止将role设置为tool

### 流式传输

现在只需要将Agent的回答流式传输给用户。至于工具调用只需要在Agent回答输出完毕之后解析完整的markdown就好了

### 文档

> TODO: 这一个功能还没做

为了减少Prompt长度，减少资源占用，同时为每个工具提供详尽的使用方法，工具的使用说明被外置在文档中

Agent在调用工具时，首先会使用`lookup_tool_docs`查阅对应的文档，然后再调用工具

## 全局记忆

全局记忆是一个markdown文档，文件名为`LINHAI.md`，其中保存着Agent需要的各类信息

全局记忆的格式为分层无序列表markdown

全局记忆的内容可以由Agent自由改写。在Agent启动时，全局记忆的内容会被附在第一条message(system prompt)后

## System Prompt设计

```markdown
# 情景

你是林海漫游，一个思维强大、擅长编程、记忆力强、措辞友好、小心谨慎的人工智能Agent

你有时会出错，有时会健忘，但是你会根据用户的需求和你自己的观察修正自己，完成任务。

# 全局记忆

全局记忆是...

- 你不应该频繁修改全局记忆，只有非常重要或者用户指定需要记忆的内容才能保存到全局记忆中
- 你只有在用户要求的时候才能清理全局记忆的内容

# 工具

你可以在Markdown中输出JSON code block来调用工具，格式如下:

```json
{
    "name": "....",
    "arguments": {
        "a": 1,
        "b": 2
    }
}
```

# 流程

## 处理用户输入

...

## 调用工具

...

# 注意

...
```

# 消息设计

LLM的消息是根据系统文件等外部信息动态生成的，本项目的消息分为两种：

1. 在llm.py中定义的Message，用以表示更加多样的消息类型，如工具处理结果/错误信息，全局记忆消息等
2. 在type_hints.py中定义的LanguageModelMessage, 和OpenAI库的LLM消息类型兼容

生成LLM回复时，Message会被动态地转换为LanguageModelMessage，以实现动态修改System Prompt、全局记忆等内容

# 项目分层设计

## utils类

### exceptions.py

定义程序运行时的各类错误

### type_hints.py

定义其他函数使用的各种类型

### config.py

从config.toml中读取配置，保存为一个TypedDict以供其他模块读取

现在暂时只用来存放LLM API的base_url, api_key和model name

### queue.py

基于asyncio.Queue的异步队列，定义各类和队列相关的操作

队列用来传输各种消息，设计类似于Golang中的chan，支持类似Golang中select的操作

支持一个select函数，这个select函数支持等到多个Queue，直到所有Queue关闭

select函数用来让Agent同时等待多个queue，Agent需要同时等待用户发来的消息、工具发来的消息等等，且用户可能会提前关闭Queue

### main.py

主函数，解析命令行参数，启动对应功能

当前支持以下子命令

- `test` 运行unittest
- `chat` 使用对应的config调用LLM聊天
- `agent` 启动Agent，让Agent和用户进行交流
    - 初始化用户和工具的Queue，把用户的消息Pipe进Queue中，然后等待Agent输出（将消息Pipe进Queue中），从Pipe中拿到Agent的输出后打印出来
    - 支持指定LINHAI.md和config.toml等位置，默认当前目录

其他地方没写好，暂时先添加调用unittest运行单元测试的功能

## Agent相关

### global_memory.py

全局记忆的实现放在`global_memory.py`中，其中实现了一个类`AgentGlobalMemory`，支持修改

### agent.py

Agent响应式地从Queue接受用户和工具的消息

这个函数实现Agent本身和初始化Agent的逻辑等，方便main.py等函数调用

## LLM对接 llm.py

提供一个Procol LanguageModel, 用于让其他模块调用LLM

LanguageModel Protocol提供`answer_stream`函数，根据输入聊天历史流式生成LLM的回答

`answer_stream`函数返回一个`Answer`对象，其设计类似`requests`库中的`Response`类，用户可以遍历这个对象，获得当前LLM的回答的每个Token，在生成完毕后可以调用对应函数获得回答的全部文本和思考的文本

llm.py应该支持打断当前回答消息的生成

## 工具 tool/

### base.py

定义工具的定义函数等，参考tool_example.py

### main.py

定义ToolManager类，这个类负责使用Queue和Agent通信，从Agent接受工具信息，调用对应的工具，并发送工具的输出

工具的输出必须可以被JSON序列化，便于展示给Agent

### tools/calculation.py

定义一个用来测试的工具：计算两个数字的和

## 外界交互

Agent持有四个Queue，用户输入消息Queue，工具输入消息Queue，用户输出消息Queue和工具输出消息Queue

因为还没有开发完毕，Agent的工具输入输出Queue可以先传一个无用的Queue

## 读取LLM响应流程

## Agent类设计

以下是伪代码

```python

class Agent:
    def __init__(self, ...):
        """
        初始化状态、保存OpenAi类、Queue、工具等
        """
    async def state_waiting_user(self):
        # 等待用户
    async def state_working(self):
        # 自动运行
    async def state_paused(self):
        # 暂停运行
    async def handle_user_message(self, ...):
        # 处理用户消息
    async def handle_tool_message(self, ...):
        # 处理工具消息
    # 因为client.chat.completions.create返回的数据比较复杂
    # 这里开几个工具函数解析里面的数据
    async def collect_tool_calls(self, ...):
        pass
    async def read_token_stream(self, ...):
        """读取LLM响应"""
        # 这里就是用async for chunk in response读取LLM响应的地方，这个函数可能会比较长
    async def run(self):
        """
        事件循环
        """
        
        while True:
            # 判断当前状态，转到对应的状态函数
            if self.state == ...:
                ...

```
