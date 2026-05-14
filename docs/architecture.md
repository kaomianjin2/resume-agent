# 项目架构图

本文档描述当前项目的已实现架构。图中模块均对应仓库中的文档或代码。

![Interview Agent 项目架构图](./architecture.svg)

## 维护规则

- 项目架构有变动时，必须同步更新 `docs/architecture.svg`。
- 架构说明有变动时，必须同步更新本文档。
- 涉及运行时入口、节点编排、节点契约、存储结构、知识库构建、检索链路、配置边界或外部服务调用的变更，均属于架构变动。

## 总览架构

```mermaid
flowchart TD
    User[用户] --> CLI[Interactive CLI<br/>src/interview_agent/cli.py]

    CLI --> Config[配置加载<br/>config/interview-agent.toml<br/>src/interview_agent/config.py]
    CLI --> KBReady[知识库 ready 检查<br/>get_knowledge_base_status]
    KBReady -->|not_ready| OfflineHint[输出离线构建命令并退出]
    KBReady -->|ready| Session[创建/读取会话<br/>SessionStore]

    CLI --> Orchestrator[普通请求编排<br/>src/interview_agent/orchestrator.py<br/>run_user_request]
    CLI --> MockFlow[模拟面试流程<br/>src/interview_agent/cli.py]
    Orchestrator --> Router[Conversation Router<br/>src/interview_agent/router.py]
    Router --> RuleRoute[规则路由]
    Router --> LLMRoute[LLM 分类兜底]
    Router --> DefaultRoute[默认 knowledge_search]
    Router --> DirectionChoice{needs_user_choice}
    DirectionChoice -->|是| UserChoice[用户选择处理方向]
    DirectionChoice -->|否| Planner

    UserChoice --> Planner
    Planner[Node Planner<br/>src/interview_agent/planner.py]
    Planner --> Executor[Node Executor<br/>src/interview_agent/executor.py]
    MockFlow --> Executor

    Executor --> Registry[Node Registry<br/>src/interview_agent/nodes/registry.py]
    Registry --> Handlers[Interview Node Handlers<br/>src/interview_agent/nodes/interview.py]

    Executor --> SQLite[(SQLite<br/>sessions / session_state / node_runs)]
    Handlers --> AgentRuntime[Structured Node Runtime<br/>src/interview_agent/agents.py]
    AgentRuntime --> Prompts[Prompt Templates<br/>src/interview_agent/prompts.py]
    AgentRuntime --> LLM[OpenAI-compatible LLM<br/>src/interview_agent/llm.py]
    AgentRuntime --> Retriever[SQLite Hybrid Retriever<br/>src/interview_agent/kb/retrieval.py]

    Retriever --> FTS[(SQLite FTS5<br/>knowledge_chunks_fts)]
    Retriever --> Embeddings[(Chunk Embeddings<br/>knowledge_chunk_embeddings)]
    Retriever --> KBChunks[(Knowledge Docs / Chunks<br/>knowledge_documents<br/>knowledge_chunks)]

    Executor --> Runs[(node_runs<br/>成功/失败/缺输入记录)]
    Executor --> State[(session_state<br/>节点输出共享状态)]
```

## 运行时调用链

```mermaid
sequenceDiagram
    participant U as 用户
    participant CLI as CLI
    participant O as Orchestrator
    participant C as Config
    participant S as SQLite Session
    participant R as Router
    participant P as Planner
    participant E as Executor
    participant N as Node Handler
    participant A as Structured Runtime
    participant K as Retriever
    participant L as LLM

    U->>CLI: 输入自然语言或 /node
    CLI->>C: load_config(config/interview-agent.toml)
    CLI->>S: get_knowledge_base_status()
    alt knowledge_base.status != ready
        CLI-->>U: 输出离线构建命令并退出
    else ready
        CLI->>S: create_session()
        CLI->>O: run_user_request()
        O->>R: route_conversation()
        R-->>O: selected_node / candidate_nodes / needs_user_choice
        opt needs_user_choice == true
            O-->>U: 询问处理方向
            U-->>O: 选择方向
        end
        O->>P: build_execution_plan()
        O->>E: execute_node(session_id, node_name)
        E->>S: 合并 session_state 与本次输入
        E->>N: 调用节点 handler
        N->>A: run_structured_node()
        A->>K: search(query, limit)
        K-->>A: rag_context
        A->>L: request_structured_output()
        L-->>A: JSON object
        A-->>N: 结构化输出
        N-->>E: 节点输出
        E->>S: 写入 node_runs
        E->>S: 成功时写入 session_state
        O-->>U: 输出执行结果
    end
```

## 离线知识库构建

```mermaid
flowchart LR
    Source[/知识库源目录<br/>/Users/cynicism/Desktop/面试/] --> Policy[文件筛选<br/>file_policy.py]
    Policy --> Parser[文本抽取<br/>parser.py<br/>md/pdf/docx]
    Parser --> Chunking[切分与 hash<br/>chunking.py]
    Chunking --> Builder[离线构建器<br/>kb/build.py]

    Config[config/interview-agent.toml] --> Builder
    Builder --> StatusBuilding[(knowledge_base_meta<br/>building)]
    Builder --> Docs[(knowledge_documents)]
    Builder --> Chunks[(knowledge_chunks)]

    Builder --> Embedder[LocalBGEEmbedder<br/>models/bge-m3<br/>local_files_only=True]
    Embedder --> VectorIndex[(knowledge_chunk_embeddings)]
    Builder --> FTS[(knowledge_chunks_fts)]
    Builder --> StatusReady[(knowledge_base_meta<br/>ready)]

    Builder -.失败.-> StatusFailed[(knowledge_base_meta<br/>failed)]
```

## 数据边界

```mermaid
erDiagram
    sessions ||--o{ session_state : stores
    sessions ||--o{ node_runs : records
    knowledge_documents ||--o{ knowledge_chunks : contains
    knowledge_chunks ||--o| knowledge_chunk_embeddings : indexed_by

    sessions {
        text session_id PK
        text created_at
        text updated_at
        text status
    }

    session_state {
        text session_id FK
        text state_key
        text state_value
        text value_type
        text updated_at
    }

    node_runs {
        text run_id PK
        text session_id FK
        text node_name
        text status
        text input_payload
        text output_payload
        text error_message
        text started_at
        text finished_at
    }

    knowledge_documents {
        text document_id PK
        text source_path
        text content_hash
        text status
        text created_at
        text updated_at
    }

    knowledge_chunks {
        text chunk_id PK
        text document_id FK
        integer chunk_index
        text content
        text created_at
    }

    knowledge_chunk_embeddings {
        text chunk_id PK
        text embedding_json
        integer dimension
        text updated_at
    }
```

## 架构约束

- 入口是交互式 CLI，不是固定流水线。
- CLI 的普通请求路径委派给 `run_user_request()`；模拟面试流程仍保留在 CLI 模块内。
- 配置固定读取 `config/interview-agent.toml`。
- 运行时只检查知识库 ready 状态，不构建知识库。
- 知识库通过离线命令构建到 SQLite。
- 节点之间只通过 SQLite `session_state` 共享数据。
- 节点执行结果统一记录到 `node_runs`。
- 路由明确时直接执行内部步骤。
- Router 通过 `needs_user_choice` 显式告诉 CLI 是否询问用户。
- CLI 只展示能力方向，不展示 `candidate_nodes` 内部节点名。
- Planner 只生成内部执行步骤，`requires_confirmation` 保留为兼容字段且固定为 `False`。
- 知识库检索使用 SQLite FTS5 和本地 bge-m3 embedding 混合排序。
