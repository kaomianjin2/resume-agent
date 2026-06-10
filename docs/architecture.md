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
    User --> DesktopShell[Tauri Desktop Shell<br/>gui/src-tauri/src/main.rs]
    DesktopShell --> ReactShell[React Web Shell<br/>gui/src/app/App.tsx]
    ReactShell --> GUIRuntime[GUI Runtime Facade<br/>src/interview_agent/gui_runtime.py]
    DesktopShell --> PythonProcess[Python Runtime Process<br/>uv run interview-agent --config config/interview-agent.toml]
    PythonProcess --> CLI

    CLI --> Config[配置加载<br/>config/interview-agent.toml<br/>src/interview_agent/config.py]
    GUIRuntime --> Config
    DesktopShell --> Config
    CLI --> KBReady[知识库 ready 检查<br/>get_knowledge_base_status]
    GUIRuntime --> KBReady
    DesktopShell --> KBReady
    KBReady -->|not_ready| OfflineHint[输出离线构建命令并退出]
    KBReady -->|ready| Session[创建/读取会话<br/>SessionStore]
    GUIRuntime --> Session

    CLI --> Orchestrator[普通请求编排<br/>src/interview_agent/orchestrator.py<br/>run_user_request]
    GUIRuntime --> Router
    GUIRuntime --> Planner
    GUIRuntime --> Executor
    GUIRuntime --> State
    GUIRuntime --> PrepVM[面试准备聚合<br/>prepare_interview_materials<br/>resume_parse -> jd_parse -> jd_match]
    PrepVM --> Executor
    PrepVM --> State
    GUIRuntime --> JobProfileVM[求职画像生成<br/>prepare_job_search_profile<br/>resume_profile -> job_search_profile / filters]
    JobProfileVM --> State
    GUIRuntime --> JobCollectionVM[求职采集编排<br/>collect_job_applications / retry_failed_job_collection_platform<br/>job_collection_progress]
    JobCollectionVM --> JobAdapterProtocol
    JobCollectionVM --> JobProgress[(collection_platform_progress)]
    JobCollectionVM --> State
    JobAdapterProtocol[求职平台适配器协议<br/>job_platform_adapters.py<br/>StandardJob / errors / fake adapter]
    SensitiveBoundary[敏感信息边界<br/>sensitive.py<br/>scan / redact / URL summary]
    JobProfileVM -.采集与投递共享契约.-> JobAdapterProtocol
    JobAdapterProtocol --> SensitiveBoundary
    GUIRuntime --> MockVM[GUI 模拟面试闭环<br/>start_mock_interview / submit_mock_answer / end_mock_interview<br/>question_generate -> mock_followup -> answer_score]
    MockVM --> Executor
    MockVM --> State
    CLI --> MockFlow[模拟面试流程<br/>src/interview_agent/mock_interview.py]
    CLI --> Rendering[结果展示层<br/>src/interview_agent/rendering.py]
    Orchestrator --> Router[Conversation Router<br/>src/interview_agent/router.py]
    Router --> RuleRoute[规则路由]
    Router --> LLMRoute[LLM 分类兜底]
    Router --> DefaultRoute[默认 knowledge_search]
    Router --> DirectionChoice{needs_user_choice}
    DirectionChoice -->|是| UserChoice[用户选择处理方向]
    DirectionChoice -->|否| Planner

    UserChoice --> Planner
    Planner[Node Planner<br/>src/interview_agent/planner.py]
    StateContracts[State Contracts<br/>src/interview_agent/state_contracts.py]
    StateContracts --> Planner
    Planner --> Executor[Node Executor<br/>src/interview_agent/executor.py]
    MockFlow --> Executor

    Executor --> Registry[Node Registry<br/>src/interview_agent/nodes/registry.py]
    StateContracts --> Registry
    StateContracts --> SessionValidation[session_state 写入校验]
    SensitiveBoundary --> SessionValidation
    Registry --> Handlers[Interview Node Handlers<br/>src/interview_agent/nodes/interview.py<br/>输出归一化]

    Executor --> SQLite[(SQLite<br/>sessions / session_state / node_runs)]
    Executor --> SensitiveBoundary
    SessionValidation --> SQLite
    Handlers --> AgentRuntime[Structured Node Runtime<br/>src/interview_agent/agents.py]
    AgentRuntime --> SensitiveBoundary
    AgentRuntime --> Prompts[Prompt Templates<br/>src/interview_agent/prompts.py]
    AgentRuntime --> LLM[OpenAI-compatible LLM<br/>src/interview_agent/llm.py]
    AgentRuntime --> Retriever[SQLite Hybrid Retriever<br/>src/interview_agent/kb/retrieval.py]

    Retriever --> FTS[(SQLite FTS5<br/>knowledge_chunks_fts)]
    Retriever --> Embeddings[(Chunk Embeddings<br/>knowledge_chunk_embeddings)]
    Retriever --> KBChunks[(Knowledge Docs / Chunks<br/>knowledge_documents<br/>knowledge_chunks)]

    Executor --> Runs[(node_runs<br/>成功/失败/缺输入记录)]
    Executor --> State[(session_state<br/>节点输出共享状态)]
    Orchestrator --> Rendering
    MockFlow --> Rendering
    Rendering --> User
```

## 运行时调用链

```mermaid
sequenceDiagram
    participant U as 用户
    participant CLI as CLI
    participant G as Rendering
    participant M as Mock Interview
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
        alt 模拟面试请求
            CLI->>M: run_mock_interview()
            M->>E: execute_node(question_generate / mock_followup)
            E->>S: 写入 node_runs / session_state
            CLI-->>U: 逐题提问、追问、输出参考答案
        else 普通请求
            CLI->>O: run_user_request()
            O->>R: route_conversation()
            R-->>O: selected_node / candidate_nodes / needs_user_choice
            opt needs_user_choice == true
                O-->>U: 询问处理方向
                U-->>O: 选择方向
            end
            O->>P: build_execution_plan()
            P->>S: 读取 state contract 判断缺失输入
            O->>E: execute_node(session_id, node_name)
            E->>S: 合并 session_state 与本次输入
            E->>N: 调用节点 handler
            N->>A: run_structured_node()
            A->>K: search(query, limit)
            K-->>A: rag_context + source metadata
            A->>L: request_structured_output()
            L-->>A: JSON object
            A-->>N: 保护来源字段后的结构化输出
            N->>N: 归一化声明输出并校验最小结构
            N-->>E: 节点输出
            E->>S: 写入 node_runs
            E->>S: 校验后写入 session_state
            O->>G: write_result() / write_line()
            G-->>U: 输出执行结果
        end
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
    job_applications ||--o| job_application_evaluations : evaluated_by
    job_applications ||--o{ application_records : tracks
    application_confirmations ||--o{ application_records : groups
    collection_tasks ||--o{ collection_platform_progress : reports

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

    job_applications {
        text job_id PK
        text platform
        text platform_job_id
        text company_name
        text title
        text location
        text detail_url
        text jd_text
        text field_confidence
        text status
        text duplicate_key
    }

    job_application_filters {
        text filter_id PK
        text hard_filters
        text ranking_preferences
        text created_at
        text updated_at
    }

    job_application_evaluations {
        text evaluation_id PK
        text job_id FK
        real score
        text hard_filter_status
        text application_message
        integer recommended
    }

    application_confirmations {
        text confirmation_batch_id PK
        text status
        text confirmed_at
        text created_at
        text updated_at
    }

    application_records {
        text record_id PK
        text job_id FK
        text confirmation_batch_id FK
        text platform
        text status
        text submitted_at
        text failure_reason
        integer duplicate_detected
    }

    collection_tasks {
        text collection_task_id PK
        text platform
        text search_keyword
        text status
    }

    collection_platform_progress {
        text progress_id PK
        text collection_task_id FK
        text platform
        integer current_page
        integer retry_count
        integer manual_takeover_required
        text status
    }
```

## 架构约束

- 入口是交互式 CLI，不是固定流水线。
- CLI 的普通请求路径委派给 `run_user_request()`；模拟面试专属流程委派给 `mock_interview.py`，并复用 CLI 提供的补输入、结果展示和取消异常回调。
- 用户可见结果展示集中在 `rendering.py`；`cli.py` 仅保留 `_write_result()`、`_write_line()` 等兼容包装和回调装配。
- GUI Runtime Facade 的面试准备入口通过 `prepare_interview_materials()` 串联 `resume_parse`、`jd_parse`、`jd_match`，返回简历摘要、岗位重点、匹配度、优势、风险和追问重点。
- GUI Runtime Facade 的求职画像入口通过 `prepare_job_search_profile()` 从已有 `resume_profile` 生成求职画像、默认搜索词、硬过滤条件、排序偏好和待确认字段，并写入 SQLite `session_state` 的 `job_search_profile`、`job_search_filters`。
- 求职采集编排器位于 `job_collection.py`，由 GUI Runtime Facade 的 `collect_job_applications()` 和 `retry_failed_job_collection_platform()` 调用；它按平台记录 `started`、`page_collected`、`detail_collected`、`completed`、`failed`、`retrying`、`manual_takeover`、`backoff` 状态，单个平台失败、风控暂停、退避或抛异常不清空其他平台结果，并把进度写入 SQLite `collection_platform_progress` 与 GUI `job_collection_progress` view model。
- 求职平台适配器协议位于 `job_platform_adapters.py`，定义标准岗位对象、搜索请求、平台执行结果、确认投递请求、投递结果、浏览器自动化边界和统一错误类型；当前为 BOSS 直聘、拉勾、猎聘适配器、采集编排器和投递执行器提供共享契约。
- 统一敏感信息边界位于 `sensitive.py`，为平台适配器、LLM prompt、`session_state`、`node_runs` 和求职存储入口提供敏感字段扫描、错误摘要脱敏和 URL 摘要能力。
- GUI Runtime Facade 的模拟面试入口通过 `start_mock_interview()`、`submit_mock_answer()`、`end_mock_interview()` 复用 `question_generate`、`mock_followup`、`answer_score`，并把当前题、追问、评分和终态 view model 写入 SQLite `session_state`。
- Tauri Desktop Shell 位于 `gui/src-tauri/`，负责承载 React Web Shell、本地文件选择、Python runtime 进程启停和窗口关闭清理。
- Desktop Shell 启动 Python runtime 时使用独立进程组；停止 runtime 或关闭窗口时清理整个进程树，避免残留 `uv` / Python 子进程。
- React Web Shell 通过 `gui/src/shared/desktop/desktopBridge.ts` 读取桌面壳状态，展示 KB 状态、Python runtime 状态、简历/JD 路径和 `lastError`。
- 配置固定读取 `config/interview-agent.toml`。
- 运行时只检查知识库 ready 状态，不构建知识库。
- 知识库通过离线命令构建到 SQLite。
- 求职投递数据独立落在 SQLite 求职表中，包含标准岗位、筛选条件、评估报告、确认批次、投递记录、采集任务和平台进度。
- 求职画像状态复用 SQLite `session_state`，不新增数据库 schema；缺失筛选维度通过待确认字段暴露给 GUI。
- 求职存储入口拒绝账号凭据、联系方式、cookie、token、浏览器 session、验证码等敏感内容落库；正常 JD、简历画像和岗位结构化字段中的 `token`、`auth`、`mobile`、普通 `session_id` 业务词不被按词面误杀。
- 清空求职数据只删除求职相关表，不删除 `sessions`、`session_state`、知识库索引或 Chrome 登录态。
- 节点之间只通过 SQLite `session_state` 共享数据。
- 节点输入、可选输入和输出 key 由 `state_contracts.py` 集中定义。
- Planner 和 Registry 复用同一份 state contract。
- `session_state` 写入先做轻量结构校验，再走统一敏感信息扫描；`search_results = []` 是合法空检索结果。
- 节点执行输入、输出和错误摘要统一记录到 `node_runs` 前先走敏感信息扫描；节点 handler 抛出敏感异常时只持久化固定脱敏失败文案。
- 路由明确时直接执行内部步骤。
- Router 通过 `needs_user_choice` 显式告诉 CLI 是否询问用户。
- CLI 只展示能力方向，不展示 `candidate_nodes` 内部节点名。
- Planner 只生成内部执行步骤，`requires_confirmation` 保留为兼容字段且固定为 `False`。
- 知识库检索使用 SQLite FTS5 和本地 bge-m3 embedding 混合排序。
- CLI 将 `config.knowledge_base.top_k` 装配为检索默认 limit；节点显式 `top_k` 输入优先。
- `knowledge_search` 的 `search_results` 以 retriever chunk 为来源基底，`chunk_id`、`source_path`、`score`、`content` 不由 LLM 覆盖。
- 空检索结果仍只写入契约字段 `search_results = []`；用户可读提示留在 CLI 展示层，不进入 `session_state`。
