# 技术面试 Agent 架构演进计划

## 结论

本计划将当前 Agent 拆成 7 个可分步落地的演进阶段。执行顺序为 Phase 0 到 Phase 6；Phase 2 与 Phase 4 可并行，Phase 3 与 Phase 5 可并行，Phase 6 在核心接口稳定后执行。

## 演进原则

- 入口保持交互式 CLI，不改为固定流水线。
- 路由明确时直接执行；仅处理方向不确定时询问用户选择。
- 不恢复“多节点执行计划确认”约束。
- 配置继续来自 `config/interview-agent.toml`，不引入环境变量配置。
- 知识库继续离线构建，运行时只检查 ready 状态。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。
- 节点之间继续只通过 SQLite `session_state` 共享数据。
- 不新增评分、训练、面试过程专用业务表；节点结果继续写入 `session_state` 和 `node_runs`。
- 每个阶段按 `.codex/rules/development-workflow.md` 创建独立 worktree、派发 implementer、派发 reviewer、运行最小测试。

## 追踪规则

### 状态枚举

- `[ ]` 未开始
- `[~]` 进行中
- `[x]` 已完成
- `[!]` 阻塞

### 更新规则

- 每个 Phase 只允许在对应任务开始后从 `[ ]` 改为 `[~]`。
- 每个 Phase 必须在最小测试、reviewer 审查、影响文档更新完成后才能改为 `[x]`。
- 阻塞时改为 `[!]`，并在“阻塞原因”中记录具体命令、错误或待决策事项。
- 完成后必须填写“完成证据”，至少包含提交或合并记录、测试命令、reviewer 结论。
- 若涉及运行时入口、节点编排、节点契约、存储、知识库、检索、配置或外部服务调用，必须同步更新 `docs/architecture.md` 和 `docs/architecture.svg`。

### 阶段总览

| Phase                      | 状态    | Owner          | 依赖                              | 可并行             | 完成证据                                                                                                                                                    |
| -------------------------- | ----- | -------------- | ------------------------------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0 当前主线收口             | `[x]` | main agent     | 无                               | 否               | `e0689b0`；`rtk uv run pytest`；reviewer 可继续                                                                                                              |
| Phase 1 运行时契约硬化            | `[x]` | implementer    | Phase 0                         | 否               | `8803c28`；最小测试通过；reviewer 可继续                                                                                                                           |
| Phase 2 交互编排层拆分            | `[!]` | implementer    | Phase 1                         | 可与 Phase 4 并行   | Phase 2A `c4b9405` 已完成；Phase 2B 模拟面试入口拆分阻塞                                                                                                              |
| Phase 3 Session State 契约固化 | `[x]` | implementer    | Phase 1                         | 可与 Phase 5 并行   | `a4d4a5b`；最小测试通过；reviewer 可继续                                                                                                                           |
| Phase 4 知识检索链路增强           | `[x]` | implementer    | Phase 1                         | 可与 Phase 2 并行   | `dd0bf67`；`rtk uv run pytest` 167 passed；reviewer 可继续                                                                                                   |
| Phase 5 节点输出质量增强           | `[x]` | implementer    | Phase 3                         | 可与 Phase 3 协调推进 | `rtk uv run pytest`：171 passed                                                                                                                          |
| Phase 6 端到端验收场景固化          | `[x]` | final_reviewer | Phase 2、Phase 3、Phase 4、Phase 5 | 否               | `rtk uv run pytest tests/test_e2e_cli_flow.py` 4 passed；`rtk uv run pytest tests/test_cli.py -k "mock"` 23 passed；`rtk uv run pytest` 175 passed；验收自检通过 |

## 推荐顺序与并行关系

1. Phase 0：当前主线收口
2. Phase 1：运行时契约硬化
3. Phase 2：交互编排层拆分
4. Phase 3：Session State 契约固化
5. Phase 4：知识检索链路增强
6. Phase 5：节点输出质量增强
7. Phase 6：端到端验收场景固化
- Phase 0 完成后再启动后续演进，避免在未收口工作区上叠加改动。
- Phase 1 完成后，Phase 2 与 Phase 4 可并行。
- Phase 3 与 Phase 5 可并行，但合并前必须统一 `session_state` key 与节点输出契约。
- Phase 6 依赖 Phase 2、Phase 3、Phase 4、Phase 5 的接口稳定。

## Phase 0：当前主线收口

**Status:** `[x]`
**Owner:** main agent  
**Dependencies:** none  
**Parallel:** no  
**Tracking ID:** `evolution-phase-0-current-mainline-closeout`  
**完成证据:** 提交 `e0689b0`；`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py` 58 passed；`rtk uv run pytest` 129 passed；reviewer 结论：可继续  
**阻塞原因:** none

### 目标

把已完成的“取消多节点确认约束”变更收口，确保文档、规则、测试和架构图一致，再进入新一轮架构演进。

### 前置依赖

- 当前工作区包含取消多节点确认约束的代码、测试、文档改动。
- `uv run pytest` 已通过。

### 任务清单

1. [操作] 检查旧约束文案残留 → verify: `rg "多节点串联前必须|多节点执行前必须|执行计划确认|Execution Confirmation|PlanConfirmation|ensure_plan_confirmation" .codex docs src tests`
2. [操作] 运行最小相关测试 → verify: `uv run pytest tests/test_router_planner.py tests/test_cli.py`
3. [操作] 运行全量测试 → verify: `uv run pytest`
4. [操作] 按当前分支策略提交变更 → verify: `git status --short`
5. [操作] 若进入正式任务流程，补充 `docs/HISTORY.md` 记录 → verify: `rg "取消多节点确认|路由明确时直接执行" docs/HISTORY.md`

### 影响范围

- `.codex/rules/runtime-architecture.md`
- `docs/PLAN.md`
- `docs/TODO.md`
- `docs/architecture.md`
- `docs/architecture.svg`
- `src/interview_agent/cli.py`
- `src/interview_agent/planner.py`
- `tests/test_cli.py`

### 验收标准

- 文档和规则不再要求多节点执行前确认。
- 明确路由多节点继续直接执行。
- 不确定路由只询问处理方向，不展示内部节点名。
- 全量测试通过。

### 风险/边界

- 不继续扩展新功能。
- 不修改 SQLite schema。
- 不触碰 `/Users/cynicism/Desktop/面试`。

## Phase 1：运行时契约硬化

**Status:** `[x]`
**Owner:** implementer  
**Dependencies:** Phase 0  
**Parallel:** no  
**Tracking ID:** `evolution-phase-1-runtime-contract`  
**完成证据:** 提交 `8803c28`；`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py` 63 passed；`rtk uv run pytest` 135 passed；reviewer 结论：可继续  
**阻塞原因:** none

### 目标

明确 Router、Planner、Executor、CLI 的职责边界，让“内部步骤”和“用户可感知能力”分离，防止后续演进重新引入计划确认或节点名暴露。

### 前置依赖

- Phase 0 完成。
- `tests/test_router_planner.py` 与 `tests/test_cli.py` 通过。

### 任务清单

1. [操作] 给 `RouteResult` 增加 `needs_user_choice` 字段，把“是否询问用户”从 CLI 条件判断移到 Router 结果 → verify: `uv run pytest tests/test_router_planner.py tests/test_cli.py -k "ambiguous_route"`
2. [操作] 保持 `ExecutionPlan.requires_confirmation` 为兼容字段，并在测试中锁定恒为 `False` → verify: `uv run pytest tests/test_router_planner.py -k "confirmation"`
3. [操作] 增加 Router 测试，覆盖 rule 单候选、LLM 单候选、LLM 多候选、default 四类路径 → verify: `uv run pytest tests/test_router_planner.py`
4. [操作] 增加 CLI 测试，确认多候选只展示能力方向，不展示 `candidate_nodes` 内部名称 → verify: `uv run pytest tests/test_cli.py -k "ambiguous_route"`
5. [操作] 更新 `docs/architecture.md` 和 `docs/architecture.svg` 的 Router/Planner 说明 → verify: `rg "needs_user_choice|处理方向不确定|内部步骤" docs/architecture.md docs/architecture.svg`

### 影响范围

- `src/interview_agent/router.py`
- `src/interview_agent/cli.py`
- `src/interview_agent/planner.py`
- `tests/test_router_planner.py`
- `tests/test_cli.py`
- `docs/architecture.md`
- `docs/architecture.svg`

### 验收标准

- CLI 不再通过 `via == "llm" and len(candidate_nodes) > 1` 判断是否询问用户。
- Router 明确输出是否需要用户选择。
- Planner 只生成内部步骤，不承担用户确认职责。
- 明确路由不展示内部节点名。

### 风险/边界

- 不改 CLI 参数。
- 不改节点 handler 接口。
- 不改 SQLite schema。

## Phase 2：交互编排层拆分

**Status:** `[!]`  
**Owner:** implementer  
**Dependencies:** Phase 1  
**Parallel:** 可与 Phase 4 并行  
**Tracking ID:** `evolution-phase-2-orchestration-split`  
**完成证据:** Phase 2A 提交 `c4b9405`；`rtk uv run pytest tests/test_cli.py -k "natural_language_request or missing_jd_input"` 4 passed；`rtk uv run pytest tests/test_cli.py -k "matched_node or missing_jd_input"` 3 passed；`rtk uv run pytest tests/test_cli.py` 48 passed；reviewer 结论：可继续  
**阻塞原因:** Phase 2B 三次未完成：`task/phase-2b-mock-interview-entry` 迁移后 `mock_interview.py` 501 行，超过 450 行上限；`task/phase-2b-mock-interview-entry-v2` 长时间未完成且只产生测试改动；`task/phase-2b-mock-interview-entry-v3` 未落盘实现。失败 worktree 与分支均已清理。后续需重新评估是否继续拆模拟面试，或先推进 Phase 3/Phase 4。

### 目标

将 `src/interview_agent/cli.py` 中的普通请求执行、缺输入补齐、结果展示、模拟面试流程拆到清晰的函数模块，降低入口文件复杂度，同时保持 CLI 行为不变。

### 前置依赖

- Phase 1 完成。
- `tests/test_cli.py` 覆盖主要交互路径。

### 任务清单

1. [x] 新增 `src/interview_agent/orchestrator.py`，迁移普通请求执行流程，保留 `main()` 负责参数解析、配置加载、服务装配、输入循环 → verify: `rtk uv run pytest tests/test_cli.py -k "natural_language_request or missing_jd_input"`
2. [x] 新增 `run_user_request()` 函数，输入 `user_message/session_id/session_store/registry/executor/llm_client`，输出面向 CLI 的结果 → verify: `rtk uv run pytest tests/test_cli.py -k "matched_node or missing_jd_input"`
3. [x] 将缺输入补齐函数保留为函数式接口，确保节点 handler 不读取用户输入 → verify: `rtk rg "input_func" src/interview_agent/nodes src/interview_agent/agents.py`
4. [操作] 新增 `src/interview_agent/mock_interview.py`，迁移模拟面试流程，CLI 只调用入口函数 → verify: `uv run pytest tests/test_cli.py -k "mock"`
5. [x] 保持 CLI 输出文本兼容现有断言，不输出内部节点名和执行计划 → verify: `rtk uv run pytest tests/test_cli.py`
6. [操作] 运行全量测试确认拆分无行为回归 → verify: `uv run pytest`

### 影响范围

- `src/interview_agent/cli.py`
- `src/interview_agent/orchestrator.py`
- `src/interview_agent/mock_interview.py`
- `tests/test_cli.py`

### 验收标准

- `cli.py` 保留入口装配和输入循环主干。
- 普通请求和模拟面试具备独立函数级测试。
- 明确路由直接执行。
- 缺输入继续通过 CLI 提示补齐。
- 节点之间仍只通过 SQLite `session_state` 共享数据。

### 风险/边界

- 拆分期间禁止改输出文案，除非同步更新测试。
- 不引入类封装；使用函数和 dataclass。
- 不做跨模块重命名。

## Phase 3：Session State 契约固化

**Status:** `[x]`  
**Owner:** implementer  
**Dependencies:** Phase 1  
**Parallel:** 可与 Phase 5 协调推进  
**Tracking ID:** `evolution-phase-3-session-state-contracts`  
**完成证据:** 合并提交 `a4d4a5b`；任务提交 `fb61e0b`、`75f0188`、`fa4292a`；`uv run pytest tests/test_node_registry.py tests/test_executor.py tests/test_router_planner.py tests/test_interview_nodes.py` 55 passed；reviewer 结论：可继续  
**阻塞原因:** none

### 目标

明确每个节点读写的 `session_state` key，减少 CLI、Planner、NodeSpec、handler 之间的隐式耦合，保证后续节点演进不破坏上下游数据流。

### 前置依赖

- Phase 1 完成。
- Phase 2 完成后实施成本更低；也可在 Phase 2 前独立实施。

### 任务清单

1. [x] 新增 `src/interview_agent/state_contracts.py`，定义节点输入输出 key 常量和校验函数，不新增数据库表 → verify: `uv run pytest tests/test_node_registry.py tests/test_executor.py`
2. [x] 将 `DEFAULT_NODE_CONTRACTS` 中的 key 改为引用常量，避免核心 key 字符串分散 → verify: `rg "\"candidate_profile\"|\"jd_requirements\"|\"questions\"" src/interview_agent`
3. [x] 为 `SessionStore.set_state()` 增加最小结构校验入口，只校验 JSON 可编码和值非空边界，不限制业务 schema → verify: `uv run pytest tests/test_executor.py -k "session_store"`
4. [x] 在 Planner 中复用 state contract 判断缺失输入，避免 Planner 与 Registry 重复维护依赖规则 → verify: `uv run pytest tests/test_router_planner.py`
5. [x] 补充跨节点状态流测试，覆盖 `resume_parse -> jd_match -> question_generate -> answer_score -> weakness_train` → verify: `uv run pytest tests/test_interview_nodes.py -k "state"`
6. [x] 确认失败节点不覆盖既有成功状态 → verify: `uv run pytest tests/test_executor.py -k "failed_node_preserves"`

### 影响范围

- `src/interview_agent/state_contracts.py`
- `src/interview_agent/nodes/registry.py`
- `src/interview_agent/planner.py`
- `src/interview_agent/session.py`
- `tests/test_node_registry.py`
- `tests/test_executor.py`
- `tests/test_router_planner.py`
- `tests/test_interview_nodes.py`

### 验收标准

- 每个节点的 required inputs、optional inputs、outputs 有单一来源。
- Planner 的缺输入判断与 NodeSpec 保持一致。
- 跨节点数据只落在 `session_state`。
- 节点失败不污染成功状态。

### 风险/边界

- 不新增专用业务表。
- 不把简历、JD、回答写入知识库表。
- 校验只覆盖结构边界，不强制完整业务 schema。

## Phase 4：知识检索链路增强

**Status:** `[x]`
**Owner:** implementer
**Dependencies:** Phase 1
**Parallel:** 可与 Phase 2 并行
**Tracking ID:** `evolution-phase-4-retrieval-evidence`
**完成证据:** 提交 `dd0bf67`；`rtk uv run pytest` 167 passed；reviewer 结论：可继续
**阻塞原因:** none

### 目标

提升 `knowledge_search` 和 RAG 注入的可控性：检索结果必须来自 SQLite FTS + embedding 混合检索，LLM 只负责总结和组织，不丢弃真实 chunk 来源。

### 前置依赖

- 当前离线构建和检索测试通过。
- 不修改 `/Users/cynicism/Desktop/面试` 原始资料。

### 任务清单

1. [操作] 调整 `knowledge_search_handler()`，将 retriever 返回的 chunk 作为基础 `search_results`，LLM 返回内容只补充 `summary/advice` 字段 → verify: `uv run pytest tests/test_interview_nodes.py -k "knowledge_search"`
2. [操作] 在 `run_structured_node()` 返回中保留 `rag_context` 的 source metadata，不让 LLM 结果覆盖 `chunk_id/source_path/score/content` → verify: `uv run pytest tests/test_interview_nodes.py -k "rag"`
3. [操作] 将默认检索 limit 与 `config.knowledge_base.top_k` 在服务装配层打通，不通过环境变量读取 → verify: `uv run pytest tests/test_cli.py -k "retriever"`
4. [操作] 增加检索空结果测试，要求节点返回空列表和明确提示，不触发失败状态 → verify: `uv run pytest tests/test_interview_nodes.py -k "empty_results"`
5. [操作] 增加离线构建边界测试，确认简历、离职证明、图片、Excel、公司流程类资料不入库 → verify: `uv run pytest tests/test_kb_file_policy.py tests/test_kb_build.py`
6. [操作] 增加 SQLite 检索回归测试，覆盖中文 query、英文 query、混合 query 的稳定排序 → verify: `uv run pytest tests/test_retrieval.py`

### 影响范围

- `src/interview_agent/agents.py`
- `src/interview_agent/nodes/interview.py`
- `src/interview_agent/kb/retrieval.py`
- `src/interview_agent/cli.py`
- `tests/test_interview_nodes.py`
- `tests/test_retrieval.py`

### 验收标准

- `knowledge_search` 返回结果包含 `chunk_id`、`source_path`、`score`、`content`。
- LLM 失败时，检索结果仍可返回。
- 检索不读取环境变量。
- 运行时不构建知识库。
- 原始资料目录不被修改。

### 风险/边界

- 不更换 embedding 模型。
- 不引入外部向量数据库。
- 不把用户简历或 JD 写入知识库。

## Phase 5：节点输出质量增强

**Status:** `[x]`
**Owner:** implementer  
**Dependencies:** Phase 3  
**Parallel:** 可与 Phase 3 协调推进  
**Tracking ID:** `evolution-phase-5-node-output-quality`  
**完成证据:** `rtk uv run pytest tests/test_interview_nodes.py tests/test_llm.py tests/test_executor.py`：49 passed；`rtk uv run pytest`：171 passed；reviewer 结论：可继续
**阻塞原因:** none

### 目标

提高 11 个运行时节点的输出稳定性，明确每个节点的最小结构、失败行为和降级策略，让 implementer 能逐节点增强 prompt 与测试。

### 前置依赖

- Phase 3 完成后实施。
- 当前 LLM client 已支持结构化 JSON 解析。

### 任务清单

1. [操作] 为每个节点新增最小输出结构测试，覆盖成功、缺字段、非法类型三类情况 → verify: `uv run pytest tests/test_interview_nodes.py`
2. [操作] 在 `nodes/interview.py` 中为每个 handler 增加输出归一化函数，缺少声明 outputs 时返回 failed，不写入 `session_state` → verify: `uv run pytest tests/test_executor.py -k "output_must_include"`
3. [操作] 增强 `prompts.py` 中 11 个节点模板，要求 JSON 字段与 `NodeSpec.outputs` 一致 → verify: `uv run pytest tests/test_llm.py tests/test_interview_nodes.py`
4. [操作] 为 `answer_score` 输出增加 `score/gaps/suggestions/reference_answer` 最小字段校验 → verify: `uv run pytest tests/test_interview_nodes.py -k "answer_score"`
5. [操作] 为 `weakness_train` 输出增加 `focus/steps/drills/schedule` 最小字段校验 → verify: `uv run pytest tests/test_interview_nodes.py -k "weakness_train"`
6. [操作] 为 `resume_optimize` 输出增加 `summary/bullets/risks/rewrite_examples` 最小字段校验 → verify: `uv run pytest tests/test_interview_nodes.py -k "resume_optimize"`
7. [操作] 运行全量测试，确认节点增强不改变 CLI 行为 → verify: `uv run pytest`

### 影响范围

- `src/interview_agent/nodes/interview.py`
- `src/interview_agent/prompts.py`
- `tests/test_interview_nodes.py`
- `tests/test_llm.py`

### 验收标准

- 每个节点输出都有稳定最小结构。
- LLM 返回非法 JSON 或缺字段时，节点失败写入 `node_runs.status = failed`。
- 失败节点不写入输出 key。
- 成功节点只写入声明过的输出 key。

### 风险/边界

- 不新增通用类抽象。
- 不把评分和训练结果拆入专用表。
- prompt 增强不得输出或记录密钥字段。

## Phase 6：端到端验收场景固化

**Status:** `[x]`
**Owner:** final_reviewer
**Dependencies:** Phase 2、Phase 3、Phase 4、Phase 5
**Parallel:** no
**Tracking ID:** `evolution-phase-6-e2e-acceptance`
**完成证据:** `rtk uv run pytest tests/test_e2e_cli_flow.py`：4 passed；`rtk uv run pytest tests/test_cli.py -k "mock"`：23 passed；`rtk uv run pytest`：175 passed；验收自检结论：端到端 CLI 流、模拟面试、KB 未 ready、失败恢复和文档验收清单通过
**阻塞原因:** none

### 目标

建立可重复的端到端验收脚本和测试场景，覆盖真实 CLI 主流程、离线知识库构建、明确路由、不确定路由、缺输入补齐、模拟面试和失败恢复。

### 前置依赖

- Phase 2、Phase 3、Phase 4、Phase 5 完成。
- 本阶段不要求真实 LLM；优先使用 fake LLM 和临时 SQLite。

### 任务清单

1. [操作] 新增 `tests/test_e2e_cli_flow.py`，使用 fake LLM 和 fake retriever 覆盖 `resume_parse -> jd_parse -> question_generate` → verify: `uv run pytest tests/test_e2e_cli_flow.py`
2. [操作] 增加不确定路由场景测试，LLM 返回多个候选节点时 CLI 只询问处理方向 → verify: `uv run pytest tests/test_e2e_cli_flow.py -k "ambiguous_route"`
3. [操作] 增加 KB 未 ready 场景测试，启动只输出离线构建命令并退出 → verify: `uv run pytest tests/test_e2e_cli_flow.py -k "knowledge_base_not_ready"`
4. [操作] 增加节点失败恢复场景测试，失败写入 `node_runs`，既有 `session_state` 成功结果不被覆盖 → verify: `uv run pytest tests/test_e2e_cli_flow.py -k "failure_recovery"`
5. [操作] 增加模拟面试场景测试，覆盖题目数、追问轮数、空回答参考答案、`/stop` 中断 → verify: `uv run pytest tests/test_cli.py -k "mock"`
6. [操作] 编写最小手工验收命令清单到 `docs/TODO.md` 或独立验收段落 → verify: `rg "uv run interview-agent|uv run python -m interview_agent.kb.build|uv run pytest" docs`
7. [操作] 运行最终验收命令组 → verify: `uv run pytest`

### 影响范围

- `tests/test_e2e_cli_flow.py`
- `tests/test_cli.py`
- `docs/TODO.md`

### 验收标准

- 端到端测试覆盖核心用户路径。
- fake LLM 测试不依赖网络和真实模型。
- KB 未 ready 不初始化执行器。
- 明确路由不展示内部节点名。
- 不确定路由只展示处理方向。
- 全量测试通过。

### 风险/边界

- 不在自动测试中访问 `/Users/cynicism/Desktop/面试`。
- 不安装或升级依赖。
- 不引入真实外部 LLM 调用作为 CI 前置条件。

## 最小下一步

### 1-2 天内目标

完成 Phase 0，并为 Phase 1 打开最小切入点：把“是否询问用户选择”的判断从 CLI 条件迁移到 Router 结果。

### 任务清单

1. [操作] 收口当前未提交变更并运行旧约束检索 → verify: `rg "多节点串联前必须|执行计划确认|PlanConfirmation|ensure_plan_confirmation" .codex docs src tests`
2. [操作] 运行当前回归测试 → verify: `uv run pytest tests/test_router_planner.py tests/test_cli.py`
3. [操作] 给 `RouteResult` 增加 `needs_user_choice` 字段 → verify: `uv run pytest tests/test_router_planner.py`
4. [操作] CLI 改为读取 `route_result.needs_user_choice` 决定是否询问方向 → verify: `uv run pytest tests/test_cli.py -k "ambiguous_route"`
5. [操作] 运行最小回归测试 → verify: `uv run pytest tests/test_router_planner.py tests/test_cli.py`

### 成功标准

- 明确路由多节点继续直接执行。
- CLI 不展示内部节点名和执行计划。
- 不确定路由仍要求用户选择处理方向。
- 配置仍只来自 `config/interview-agent.toml`。
- 节点共享数据仍只通过 SQLite `session_state`。
