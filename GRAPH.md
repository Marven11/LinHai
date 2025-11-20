# LinHai Agent 运行时交互流程图

```mermaid
flowchart TD
    %% 启动流程
    A[main.py: 程序启动] --> B[创建 GroupChat]
    B --> C[创建 Agent]
    C --> D[注册消息队列和成员]
    
    %% Agent 主循环
    D --> E{Agent 状态机}
    E -->|waiting_user| F[等待用户状态]
    E -->|working| G[自动运行状态]
    
    %% 等待用户状态
    F --> H[监听 user_message 队列]
    H --> I{收到用户消息?}
    I -->|是| J[处理用户消息]
    I -->|否| F
    
    %% 自动运行状态
    G --> K{user_message 队列非空?}
    K -->|是| L[接收并处理用户消息]
    K -->|否| M[生成响应]
    
    %% 消息处理
    J --> M
    L --> M
    
    %% generate_response 函数核心部分（用颜色标记）
    M --> N[选择 LLM 模型]
    N --> O[调用 LLM.answer_stream]
    O --> P[流式生成回答]
    P --> Q{解析工具调用?}
    Q -->|有工具调用| R[开始新一轮工具调用]
    R --> S[逐个调用 AgentToolcall.call_tool]
    S --> T[处理工具结果]
    T --> U[保存对话历史]
    Q -->|无工具调用| U
    
    %% 工具调用详细流程
    S --> V[AgentToolcall.call_tool]
    V --> W{需要用户确认?}
    W -->|是| X[等待用户确认]
    W -->|否| Z[ToolManager.process_tool_call]
    X --> Y{用户确认?}
    Y -->|是| Z
    Y -->|否| AA[取消工具调用]
    Z --> BB[执行具体工具函数]
    BB --> CC[返回工具结果]
    CC --> T
    
    %% 状态转移
    U --> E
    
    %% 插件系统
    PL[插件系统 Lifecycle] -.-> M
    PL -.-> P
    PL -.-> Q
    PL -.-> V
    PL -.-> BB
    
    %% 关键类说明
    classDef agentClass fill:#e1f5fe
    classDef messageClass fill:#f3e5f5
    classDef toolClass fill:#e8f5e8
    classDef llmClass fill:#fff3e0
    classDef pluginClass fill:#fce4ec
    classDef generateResponseClass fill:#e8f5e8,stroke:#4caf50,stroke-width:2px
    
    class A,B,C,D,E,F,G,H,I,J,K,L agentClass
    class M,N,O,P,Q,R,S,T,U generateResponseClass
    class PL pluginClass
    class V,W,X,Y,Z,AA,BB,CC toolClass
```

## 关键类交互说明

### 核心 Agent 类
- **Agent**: 主控制器，管理状态机和整体流程
- **GroupChat**: 消息总线，负责类间通信和解耦
- **AgentMessage**: 消息处理器，管理消息队列和历史
- **AgentToolcall**: 工具调用处理器

### LLM 相关
- **LanguageModel**: LLM 接口协议
- **OpenAi**: OpenAI API 实现
- **Answer**: 流式回答接口

### 工具系统
- **ToolManager**: 工具管理器
- **ToolSet**: 工具集合
- **MCPConnector**: MCP 服务器连接器

### 插件系统
- **Lifecycle**: 生命周期管理器，统一管理各种检查插件

## 主要交互流程

1. **启动流程**: main.py → GroupChat → Agent → 注册队列和成员
2. **状态循环**: Agent 在 waiting_user 和 working 状态间切换
3. **消息处理**: 接收用户消息 → 处理 → 生成响应
4. **generate_response 函数**: 负责LLM响应生成、工具调用触发和结果处理（绿色边框标记）
5. **工具调用**: AgentToolcall.call_tool 处理具体工具执行逻辑
6. **插件拦截**: 插件系统在关键节点进行各种检查和拦截

## 元素颜色说明

- **绿色边框**: `generate_response` 函数内的核心步骤
- **蓝色**: Agent 核心类和状态机相关
- **紫色**: 工具调用相关类
- **粉色**: 插件系统
- **橙色**: LLM 相关类

这个流程图展示了 LinHai Agent 运行时各个核心类之间的交互关系，忽略 utility 类，重点关注主要的控制流和数据流喵~