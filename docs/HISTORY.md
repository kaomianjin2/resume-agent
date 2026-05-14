# 功能变更历史

本文件记录已完成、已测试、已通过审查的新功能变更。

## 记录规则

- 新功能开发完成后记录。
- 最小必要测试通过后记录。
- `reviewer` 审查通过后记录。
- 任务分支合并到主分支后、推送主分支前记录。

## 记录模板

```markdown
## YYYY-MM-DD - Task N: 功能名称

- 测试命令：`rtk uv run pytest ...`
- reviewer 结论：可继续
- 影响范围：文件 / 函数 / 接口
- 变更摘要：
  - ...
```

## 历史记录

## 2026-05-14 - Phase 4: 知识检索链路增强

- 测试命令：`rtk uv run pytest tests/test_interview_nodes.py -k "knowledge_search or rag or empty_results"`；`rtk uv run pytest tests/test_cli.py -k "retriever or knowledge_search"`；`rtk uv run pytest tests/test_kb_file_policy.py tests/test_kb_build.py`；`rtk uv run pytest tests/test_retrieval.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/agents.py` / `run_structured_node()`、`_preserve_rag_source_metadata()`；`src/interview_agent/nodes/interview.py` / `knowledge_search_handler()`；`src/interview_agent/kb/retrieval.py` / `SQLiteHybridRetriever.search()`、`hybrid_search()`；`src/interview_agent/cli.py` / 服务装配与知识检索结果展示；`src/interview_agent/kb/file_policy.py`
- 变更摘要：
  - `knowledge_search` 以 retriever chunk 为 `search_results` 基底，保留 `chunk_id`、`source_path`、`score`、`content`，LLM 只补充非来源字段。
  - RAG 输出合并时保护 source metadata，避免 LLM 覆盖真实 chunk 来源。
  - CLI 装配层将 `config.knowledge_base.top_k` 传给默认检索 limit，显式 `top_k` 输入仍优先。
  - 空检索结果保持 `search_results = []` 的节点契约，用户提示留在 CLI 展示层。
  - 离线构建边界新增公司流程资料排除，并补齐中文、英文、混合 query 的混合检索排序回归。

## 2026-05-14 - Phase 3: Session State 契约固化

- 测试命令：`uv run pytest tests/test_node_registry.py tests/test_executor.py tests/test_router_planner.py tests/test_interview_nodes.py`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/state_contracts.py`；`src/interview_agent/nodes/registry.py` / `DEFAULT_NODE_CONTRACTS`；`src/interview_agent/planner.py` / `build_execution_plan()`；`src/interview_agent/session.py` / `SessionStore.set_state()`、`write_session_state()`；`src/interview_agent/executor.py` / `NodeExecutor.execute_node()`
- 变更摘要：
  - 新增集中 state contract，统一定义节点输入、可选输入和输出 key。
  - Registry 与 Planner 复用同一契约来源，减少节点依赖规则重复维护。
  - Session state 写入增加轻量结构校验，失败输出记录为 failed node_run，不污染既有成功状态。
  - 保留 `knowledge_search` 空检索结果的合法成功态：`search_results = []`。

## 2026-05-14 - Phase 2A: 普通请求编排入口拆分

- 测试命令：`rtk uv run pytest tests/test_cli.py -k "natural_language_request or missing_jd_input"`；`rtk uv run pytest tests/test_cli.py -k "matched_node or missing_jd_input"`；`rtk uv run pytest tests/test_cli.py`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/cli.py` / `main()`；`src/interview_agent/orchestrator.py` / `run_user_request()`；`tests/test_cli.py`
- 变更摘要：
  - 新增 `run_user_request()` 承接普通请求编排路径。
  - `cli.main()` 保留启动、输入循环和模拟面试分支，普通请求委派到编排模块。
  - 保持 CLI 参数、节点 handler 接口、SQLite schema、配置和用户可见输出不变。

## 2026-05-14 - Phase 1: 运行时契约硬化

- 测试命令：`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/router.py` / `RouteResult`、`route_conversation()`；`src/interview_agent/cli.py` / `_select_node_for_route()`；`src/interview_agent/planner.py` / `ExecutionPlan`；`docs/architecture.md`；`docs/architecture.svg`
- 变更摘要：
  - `RouteResult` 新增 `needs_user_choice`，Router 统一输出是否需要用户选择。
  - CLI 改为读取 Router 显式契约，不再根据来源或候选数量自行推断。
  - `ExecutionPlan.requires_confirmation` 保持兼容字段并固定为 `False`。
  - 架构文档同步 Router/Planner 职责边界。

## 2026-05-14 - Phase 0: 当前主线收口

- 测试命令：`rtk uv run pytest tests/test_router_planner.py tests/test_cli.py`；`rtk uv run pytest`
- reviewer 结论：可继续
- 影响范围：`src/interview_agent/cli.py` / `_select_node_for_route()`；`tests/test_cli.py`；`docs/EVOLUTION_PLAN.md`
- 变更摘要：
  - 取消多节点确认约束收口完成，路由明确时继续直接执行。
  - 修复规则路由多候选时未询问处理方向的问题。
  - 补充规则路由多候选回归测试，确认不展示内部节点名。
